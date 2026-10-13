"""Gold-blind extraction of explicitly asserted ASR content; never correct words.

The extractor receives only a model answer. Neither targets, audio, gold, nor
scores can select a substring. Null means no recoverable transcript, not an
assertion of silence. Bare yes/no and short ambiguous words are retained.
"""

import collections,hashlib,json,re

from pathlib import Path

def unwrap(s,rules):
 for _ in range(3):
  old=s
  if s.startswith('```') and s.endswith('```'):
   s=re.sub(r'^```(?:json|text)?\s*\n?', '',s).removesuffix('```').strip();rules.append('outer_code_fence')
  try:
   obj=json.loads(s)
  except (ValueError,TypeError):obj=None
  if isinstance(obj,str):s=obj.strip();rules.append('json_string')
  elif isinstance(obj,dict):
   keys=[k for k in ['transcript','transcription','text'] if isinstance(obj.get(k),str)]
   if len(keys)==1:s=obj[keys[0]].strip();rules.append('explicit_json_transcript_field')
  if s==old:break
 return s

REFUSAL=re.compile(r"(?:\b(?:I(?:'m| am) (?:sorry|not sure|unable)|I (?:can(?:not|'t)|don(?:'t|’t) have)|(?:could|can) you (?:please )?provide).{0,160}(?:transcrib|transcript|speech|audio|context|information|asking)|\b(?:speech content|actual speech|audio (?:content|data|recordings?)) (?:is(?:n't| not)|has(?:n't| not) been|was(?:n't| not)) (?:provided|included|given)|\bI(?:'m| am) sorry,? (?:but )?I (?:can't|cannot) do that|\bI(?:'m| am) not sure what you(?:'re| are) asking)",re.I|re.S)

LABEL=re.compile(r"(?:(?:the |their )?(?:human |selected |full |entire |english |actual |repeated )?(?:transcript(?:ion)?|speech(?: content)?|text|content)(?: (?:of|in|from) [^\n:]{1,65})?\s+(?:is(?: as follows)?|is transcribed (?:as follows|below))\s*(?::|(?=[\"“]))|(?:the )?(?:human )?(?:speaker|person) says\s*:|(?:transcript(?:ion)?|trans)\s*:)\s*",re.I)

CHAT_SUFFIX=re.compile(r"[.\s]*(?:If you have (?:any )?(?:other |further )?(?:questions|thoughts)|If you (?:need|want) (?:any |more |further )|Feel free to (?:ask|let me know)|Let me know if you).*$",re.I|re.S)

def extract(raw):
 rules=[];s=unwrap(raw.strip(),rules);flags=[]
 # Remove only a conventional assistant suffix, outside an explicitly quoted answer.
 closing=CHAT_SUFFIX.search(s)
 # Do not remove the same words when INSIDE the claimed transcript.
 outside_quotes=closing and s[:closing.start()].count('"')%2==0
 s2=CHAT_SUFFIX.sub('',s).strip() if outside_quotes else s
 if s2!=s and ('"' in s or REFUSAL.search(s)):
  s=s2;rules.append('assistant_closing_offer')
 s=s.strip()
 if s.startswith('""') and (len(s)==2 or s[2:].startswith(('.', '\n'))):
  return '',rules+['explicit_empty_answer'],'explicit_empty',flags
 # Missing braces around an explicit transcript field, or "trans: ...".
 m=re.match(r'^"?(?:transcript(?:ion)?|trans)"?\s*:\s*(.*)$',s,re.I|re.S)
 if m:s=m.group(1).strip();rules.append('transcript_label')
 s=unwrap(s,rules)
 if len(s)>1 and s[0] in '"“' and s[-1] in '"”':
  s=s[1:-1].strip();rules.append('outer_quote')
 # Answer-declaring labels, with quotes furnishing a precise endpoint.
 matches=list(LABEL.finditer(s))
 if matches:
  m=matches[0];tail=s[m.end():].strip()
  if tail.startswith(('"','“')):
   close='”' if tail[0]=='“' else '"';end=tail.find(close,1)
   if end>=1:s=tail[1:end];rules.append('explicit_labeled_quote')
   else:s=tail[1:];rules.append('explicit_labeled_quote_truncated');flags.append('truncated_candidate_preserved')
  elif '\n\n' not in tail and len(tail)<1500 and tail:
   s=tail;rules.append('explicit_labeled_text')
 # Known response form: spatial preface, blank line, a single quoted answer.
 if '\n\n' in s and re.match(r'^(?:The (?:speaker|only speaker|following)|We have received|I see the need)',s):
  m=re.search(r'\n\n"([^"\n]*)"\s*$',s)
  if m:s=m.group(1);rules.append('spatial_preface_quoted_answer')
 # Single segment wrapper; do not merge speakers or select among alternatives.
 m=re.fullmatch(r'\[[\d.]+\s*,\s*[\d.]+\) seconds:\s*"(.*)"',s,re.S)
 if m:s=m.group(1);rules.append('single_segment_timestamp')
 s=unwrap(s.strip(),rules)
 if s.startswith('"') and s.endswith('".'):
  s=s[1:-2];rules.append('outer_quote_with_period')
 # Explicit no-target statements can assert an empty transcript; inability cannot.
 if re.fullmatch(r'The empty string\s*""\.?',s,re.I):
  return '',rules+['explicit_empty_answer'],'explicit_empty',flags
 if re.search(r'(?:no human (?:in|within|satisfies|matches)|no human speech (?:in|that matches)|no (?:human )?speaker (?:in|within|satisfies|matches)|speaker is not in the specified region|no one (?:in|within) the (?:specified|given) region|region you mentioned doesn.t seem to contain any human speech)',s,re.I) and ('empty string' in s.lower() or len(s)<250):
  return '',rules+['explicit_no_target_claim'],'explicit_empty',flags
 if not s:
  if 'transcript_label' in rules and not re.search(r':\s*""',raw):
   return None,rules+['label_without_content'],'no_transcript',flags
  return '',rules,'explicit_empty',flags
 if REFUSAL.search(s):return None,rules+['no_transcript_refusal_or_missing_information'],'no_transcript',flags
 if re.search(r"(?:information given doesn.t include any speech content|doesn.t contain any human speech to transcribe|I.m still not sure what you.re asking)",s,re.I):
  return None,rules+['no_transcript_refusal_or_missing_information'],'no_transcript',flags
 if s.lower() in {'recorded speech content goes here.','transcribed speech'}:
  return None,rules+['placeholder_not_transcript'],'no_transcript',flags
 # Unambiguous non-ASR output shapes.
 if re.fullmatch(r"(?:[a-z]+ o'clock; (?:up|down); [\d.]+(?: m)?|(?:left|right), (?:front|behind), (?:above|below); [\d.]+m)",s,re.I):
  return None,rules+['spatial_answer_instead_of_words'],'no_transcript',flags
 if re.fullmatch(r'[\d\s.,;:+\-\[\]()m]+',s) and re.search(r'\d',s) and not any(x in rules for x in ['transcript_label','explicit_json_transcript_field','explicit_labeled_quote','explicit_labeled_quote_truncated','explicit_labeled_text']):
  return None,rules+['numeric_only_nontranscript'],'no_transcript',flags
 if re.fullmatch(r'\[[\d.]+,[\d.]+\) seconds',s) or re.fullmatch(r'(?:R\d+:\s*)+',s):
  return None,rules+['time_or_receiver_labels_only'],'no_transcript',flags
 if re.fullmatch(r'(?:The (?:man|woman|person) is speaking\.|The speaker is a (?:man|woman)\.)',s):
  return None,rules+['speaker_description_not_transcript'],'no_transcript',flags
 time_pattern=r'At scene time [\d.]+ s, while this person is emitting speech:\s*"([^"\n]*)"'
 parts=re.findall(time_pattern,s)
 if parts and not re.sub(time_pattern,'',s).strip(' .\n'):
  return ' '.join(parts),rules+['time_preface_quoted_speech'],'candidate',flags+(['anchor_segments_joined_without_deduplication'] if len(parts)>1 else [])
 m=re.fullmatch(r'The human\x27s speech:\s*"([^"\n]*)"\.?',s)
 if m:return m.group(1),rules+['explicit_labeled_quote'],'candidate',flags
 if re.match(r'At scene time [\d.]+ s, while this person is emitting speech:',s):
  return None,rules+['query_echo_not_transcript'],'no_transcript',flags
 # Extended reasoning with no extracted candidate remains an explicit failure.
 if '\n' in s and re.search(r'(?:### Step|Let[’\x27]s (?:compute|suppose)|We (?:are|need) to (?:identify|transcribe)|spatial (?:conditions|constraints)|world coordinate)',s,re.I) and not any(x.startswith('explicit_labeled') for x in rules):
  return None,rules+['reasoning_without_selected_transcript'],'no_transcript',flags
 if s.lower().strip('.!') in {'yes','no','same','speech','music','music; speech','left','right','yes or no','right zero padding'}:
  flags.append('ambiguous_short_answer_retained_not_evidence_of_asr')
 if len(s)>1500:flags.append('long_or_repetitive_candidate_preserved')
 return s,rules,'candidate',flags
