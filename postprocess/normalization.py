"""Deterministic syntax repairs only; never infer values, identities, or frames."""
import ast,json,re,math
def loads(text):
 v=json.loads(text)
 json.dumps(v,allow_nan=False)
 return v
ASR={'DOA_RANGE_ASR','C2_REGION_ASR','SPATIAL_ASR','WORLD_TRAJECTORY_ASR'}
def parse(text,task,repair=False):
 s=text.strip();rules=[]
 if s.startswith('```') and s.endswith('```'):
  s=s.split('\n',1)[-1].rsplit('```',1)[0].strip();rules.append('strip_code_fence')
 if task in ASR:
  try:v=loads(s)
  except (ValueError,TypeError):v=None
  if isinstance(v,str):return v,rules+['decode_json_string']
  return s,rules
 try:
  v=loads(s)
  if repair and task in {'DOA','C1_SETLOC'} and isinstance(v,list) and v and all(type(x) in (int,float) for x in v):return [v],rules+['wrap_single_point']
  return v,rules
 except (ValueError,TypeError):pass
 if not repair:return text,rules
 # Complete JSON embedded in explanation: accept only one candidate and only the expected shape.
 expected=dict if task.endswith('TRAJECTORY') else list if task in {'DOA','TEXT_DOA','C1_SETLOC','C3_TEXTLOC'} else (float,int)
 candidates=[];decoder=json.JSONDecoder()
 for i,c in enumerate(s):
  if c not in '[{':continue
  try:
   v,end=decoder.raw_decode(s[i:]);json.dumps(v,allow_nan=False)
  except ValueError:continue
  if isinstance(v,expected):candidates.append((i,i+end,v))
 maximal=[c for c in candidates if not any(d[0]<c[0] and d[1]>=c[1] for d in candidates)]
 if len(maximal)==1:return maximal[0][2],rules+['extract_single_json']
 for value,label in [(s,'python_literal'),('['+s+']','outer_brackets')]:
  try:v=ast.literal_eval(value)
  except (ValueError,SyntaxError):continue
  try:v=json.loads(json.dumps(v,allow_nan=False))
  except (ValueError,TypeError):continue
  if task in {'DOA','C1_SETLOC'} and isinstance(v,list) and v and all(type(x) in (int,float) for x in v):v=[v];label+=';wrap_single_point'
  if isinstance(v,expected):return v,rules+[label]
 return text,rules
