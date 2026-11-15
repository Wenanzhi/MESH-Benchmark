import {Player, parseWav, decodeFOA, sha256, waveform} from './audio.js';
import {downloadAudio} from './audio-download.mjs';
import {viewName, asrTasks, statusLabels, outputStatus, displayOutput, metricLabel, spatialValues, positionAt, assertBinding} from './data-utils.mjs';

const $ = id => document.getElementById(id);
const node = (tag, text, cls) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; };
const colors = ['#4778b9','#a261a6','#cb713c','#6478a9','#539786','#c59529','#b96174','#6d8d3c','#678c9d','#bf7159','#8861b6','#245d51'];
let index, baselines, provenance, questions, questionMap, filtered = [], page = 0, current = null, loadToken = 0, audioToken = 0, audioAbort = null, currentWave = [];
const PAGE_SIZE = 30, overlays = new Set(), jsonCache = new Map();
const player = new Player(time => { if (current) { $('clock').value = `${time.toFixed(2)} / ${current.scene.duration.toFixed(2)} s`; $('timeline').value = time; draw(time); drawWave(time); $('play').textContent = player.playing ? 'Ⅱ Pause' : '▶ Listen'; } });
async function fetchJSON(url) {
  if (jsonCache.has(url)) return jsonCache.get(url);
  const response = await fetch(url, {signal: AbortSignal.timeout(45000)});
  if (!response.ok) throw Error(`Could not load ${new URL(url, location.href).pathname} (HTTP ${response.status}).`);
  const bytes = await response.arrayBuffer();
  if (provenance && url.startsWith(provenance.scene_asset_base)) {
    const path = url.slice(provenance.scene_asset_base.length);
    if (await sha256(bytes) !== provenance.scene_asset_sha256[path]) throw Error('Scene asset checksum mismatch.');
  }
  const data = JSON.parse(new TextDecoder().decode(bytes));
  jsonCache.set(url, data); if (jsonCache.size > 18) jsonCache.delete(jsonCache.keys().next().value);
  return data;
}
async function fetchShard(id) {
  const path = `shards/${id.slice(0,2)}.json.gz`, url = `data/${path}`;
  if (!jsonCache.has(url)) {
    const response = await fetch(url, {signal: AbortSignal.timeout(45000)});
    if (!response.ok) throw Error(`Result shard could not be loaded (HTTP ${response.status}).`);
    const bytes = await response.arrayBuffer();
    if (await sha256(bytes) !== provenance.shard_sha256[path]) throw Error('Result shard checksum mismatch.');
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    jsonCache.set(url, JSON.parse(await new Response(stream).text()));
    if (jsonCache.size > 18) jsonCache.delete(jsonCache.keys().next().value);
  }
  const record = jsonCache.get(url)[id];
  if (!record) throw Error('Question absent from its result shard.');
  return record;
}
function setTab(id) {
  for (const [tab, panel] of [['explore','explore'],['results','published'],['coverage','coverage']]) {
    $(`${tab}-tab`).setAttribute('aria-selected', String(id === tab)); $(panel).hidden = id !== tab;
  }
}
for (const id of ['explore','results','coverage']) $(`${id}-tab`).onclick = () => setTab(id);

function filterQuestions() {
  const query = $('search').value.trim().toLowerCase(), view = $('view').value, mode = $('mode').value, task = $('task').value;
  const archived = new Set(index.archived_examples);
  filtered = questions.filter(q => (!view || q.setting === view) && (!mode || q.mode === mode) && (!task || q.task === task)
    && (!$('only-archived').checked || archived.has(q.id)) && (!query || `${q.id} ${q.scene} ${q.room} ${q.base}`.includes(query)));
  page = 0; renderList();
}
function renderList() {
  $('count').textContent = `${filtered.length.toLocaleString()} questions`;
  $('page-count').textContent = `${page + 1} / ${Math.max(1,Math.ceil(filtered.length/PAGE_SIZE))}`;
  $('prev-page').disabled = page === 0; $('next-page').disabled = (page + 1) * PAGE_SIZE >= filtered.length;
  $('question-list').replaceChildren();
  for (const q of filtered.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE)) {
    const b = node('button', undefined, 'question-item'); b.dataset.id = q.id; b.setAttribute('aria-current', String(q.id === current?.q.id));
    b.append(node('strong', `${index.tasks[q.task].code} · ${q.mode}`),node('span', `${q.room} · ${q.id.slice(0,10)}…`));
    b.title = `${q.id}\n${index.tasks[q.task].name}`; b.onclick = () => selectQuestion(q.id); $('question-list').append(b);
  }
  if (!filtered.length) $('question-list').append(node('p','No matching questions. Change the filters.','small'));
}
for (const id of ['search','view','mode','task','only-archived']) $(id).addEventListener('input',filterQuestions);
$('reset-filters').onclick = () => { for (const id of ['search','view','mode','task']) $(id).value = ''; $('only-archived').checked = false; filterQuestions(); };
$('prev-page').onclick = () => {page--;renderList();}; $('next-page').onclick = () => {page++;renderList();};
$('diagnostics').onchange = () => {if ($('diagnostics').value) selectQuestion($('diagnostics').value);};
$('copy-link').onclick = async () => {try {await navigator.clipboard.writeText(location.href);$('copy-link').textContent='Copied';setTimeout(()=>$('copy-link').textContent='Copy link',1200);} catch { $('copy-link').textContent='Use the address bar'; }};

async function selectQuestion(id) {
  const token = ++loadToken, q = questionMap.get(id);
  if (!q) { $('global-status').hidden=false; $('global-status').textContent='The linked question ID is not part of this release.'; return; }
  ++audioToken; audioAbort?.abort(); player.reset(); current = null; overlays.clear(); currentWave = [];
  $('detail').setAttribute('aria-busy','true'); $('detail-error').hidden=true; $('scene-content').hidden=true;
  $('question-title').textContent = index.tasks[q.task].name; $('question-id').textContent=`Question ${q.id} · Scene ${q.scene}`;
  $('question-tags').replaceChildren(...[viewName(q.setting),q.mode,index.tasks[q.task].code].map(t=>node('span',t,'tag')));
  $('case-note').hidden = !index.archived_examples.includes(id);
  $('case-note').textContent = 'Published diagnostic case: selected for analysis in the paper, not a representative random example.';
  history.replaceState(null,'',`?q=${encodeURIComponent(id)}`);
  $('diagnostics').value = index.archived_examples.includes(id) ? id : '';
  try {
    const base = provenance.scene_asset_base;
    const [scene,reference,result] = await Promise.all([fetchJSON(`${base}data/scenes/${q.scene}.json`),fetchJSON(`${base}data/references/${q.scene}.json`),fetchShard(id)]);
    if (token !== loadToken) return;
    const {input,gold} = assertBinding(q,scene,reference,result);
    current = {q,scene,reference,result,input,gold};
    for (const [model,r] of Object.entries(result.outputs)) if (r.status === 'available' && !asrTasks.has(q.task)) overlays.add(model);
    player.duration = scene.duration; player.receiver = input.receiver_ids[0];
    $('receiver').replaceChildren(...input.receiver_ids.map(r=>{const o=node('option',r);o.value=r;return o;}));
    $('timeline').max=scene.duration; $('timeline').value=0; $('clock').value=`0.00 / ${scene.duration.toFixed(2)} s`;
    $('play').disabled=false; $('play').textContent='▶ Listen'; $('audio-status').textContent='Audio loads on demand; the time cursor also works before playback.';
    $('scene-facts').textContent=`${q.room} · ${q.humans} human${q.humans===1?'':'s'} · ${q.receivers} receiver${q.receivers===1?'':'s'} · ${scene.duration.toFixed(1)} s · SNR ${q.snr} dB · ${q.motion.replaceAll('_',' ')}`;
    $('input-condition').textContent = q.setting === 'edge' ? 'One recording + peer metadata' : 'Synchronized receiver recordings';
    $('cue').textContent = summarizeCue(input.query);
    $('prompt').textContent=input.prompt;
    $('input-json').textContent=JSON.stringify({query:input.query,receiver_ids:input.receiver_ids,time_window_samples:input.time_window_samples,audio:input.audio},null,2);
    $('reference').textContent=answerSummary(gold.output,q.task);
    $('reference-json').textContent=JSON.stringify(gold,null,2);
    $('output-count').textContent=`${Object.keys(result.outputs).length} / ${baselines.length} outputs archived`;
    renderBaselines(); $('scene-content').hidden=false; renderList(); draw(0); drawWave(0);
  } catch (e) { if(token===loadToken){$('detail-error').textContent=`${e.message} Select another question or reload to retry.`;$('detail-error').hidden=false;} }
  finally {if(token===loadToken)$('detail').setAttribute('aria-busy','false');}
}
function summarizeCue(query) {
  if (!query || !Object.keys(query).length) return 'Use the audio and permitted scene information to answer the task.';
  if(query.transcript)return `Locate the speaker saying: “${query.transcript}”`;
  if(query.region)return `Transcribe speech inside the world-space box from [${query.region.min_xyz_m.join(', ')}] to [${query.region.max_xyz_m.join(', ')}] meters. Return an empty transcript when no speaker matches.`;
  if(query.anchors)return query.anchors.map(a=>`At ${a.time_s.toFixed(1)} s: ${[a.doa_deg?`azimuth ${a.doa_deg[0]}°, elevation ${a.doa_deg[1]}°`:null,a.distance_m!==undefined?`distance ${a.distance_m} m`:null].filter(Boolean).join('; ')}.`).join('\n')+`\nTranscribe all speech from the matching speaker. Tolerances: ${[query.angular_tolerance_deg!==undefined?`${query.angular_tolerance_deg}°`:null,query.distance_tolerance_m!==undefined?`${query.distance_tolerance_m} m`:null].filter(Boolean).join(', ')}.`;
  if(query.cue_type==='world_trajectory')return `Transcribe all speech from the speaker following the supplied world trajectory (${query.frames.length} anchors, ${query.position_tolerance_m} m tolerance). The query path is drawn in orange; exact anchors are available below.`;
  const sector=query.azimuth_sector_deg||query.initial_sector_deg;
  if(sector)return `Locate the source in azimuth sector [${sector.join(', ')}]°${query.selection_time_s!==undefined?` at ${query.selection_time_s.toFixed(1)} s`:''}. Angles are relative to the focal receiver.`;
  if(query.source_count!==undefined)return `Localize all ${query.source_count} audible speech sources specified by this question.`;
  if(query.human_source_count!==undefined)return `Localize ${query.human_source_count} human source${query.human_source_count===1?'':'s'} using the supplied recording${current?.input.receiver_ids.length>1?'s':''}.`;
  return 'Use the exact public query below to identify the target and required output.';
}
function answerSummary(output, task) {
  if (task.includes('TRAJECTORY') && !asrTasks.has(task) && output && typeof output === 'object') {
    const frames=output.frames || (output.tracks||[]).flatMap(t=>t.frames||[]);
    return `${output.tracks?`${output.tracks.length} tracks · `:''}${frames.length} submitted frames · ${frames.filter(f=>f.active).length} active frames\nUse the time cursor for the spatial view; expand below for every numeric value.`;
  }
  return typeof output === 'string' ? displayOutput(output) : JSON.stringify(output);
}
function renderBaselines() {
  const {result,q,gold} = current; $('baseline-rows').replaceChildren();
  baselines.forEach((b,i)=>{
    const record = result.outputs[b.id], metric=result.metrics[b.id], status=outputStatus(record);
    const row=node('article',undefined,'baseline'); row.dataset.model=b.id;
    const head=node('div',undefined,'baseline-head'),name=node('div',undefined,'baseline-name');
    name.append(node('strong',b.name),node('small',`${b.input} · ${b.id}`));
    const score=node('div',undefined,'metric'), [value,label]=metricLabel(metric,q.task,gold.output==='');score.append(node('span',value),node('small',label));
    head.append(name,node('span',statusLabels[status]||status,`status ${status}`),score);row.append(head);
    if (record) {
      row.append(node('div',answerSummary(record.output,q.task),'answer'));
      if (status==='available'&&!asrTasks.has(q.task)) {
        const label=node('label',undefined,'overlay'),check=node('input');check.type='checkbox';check.checked=overlays.has(b.id);check.dataset.model=b.id;
        check.onchange=()=>{check.checked?overlays.add(b.id):overlays.delete(b.id);draw(player.position);};
        label.style.color=colors[i];label.append(check,document.createTextNode('Overlay this prediction'));row.append(label);
      }
    } else row.append(node('p','The frozen metric is available. The original answer is not in this public archive.','missing'));
    const detail=node('details');detail.append(node('summary',record?'Raw answer, complete values & evaluation record':'Metric record & configuration provenance'));
    if(record){detail.append(node('h3','Raw answer'),node('pre',record.raw_text===null?'Raw text not archived':record.raw_text),node('h3','Reviewed output (exact)'),node('pre',JSON.stringify(record.output,null,2)),node('h3','Original task-scoring record'),node('pre',JSON.stringify(record.scored,null,2)));}
    const source=record?`manuscript/notes/${record.source}`:null;
    detail.append(node('pre',JSON.stringify({sample_id:q.id,task_id:q.task,receivers:current.input.receiver_ids,configuration:b.id,input:b.input,information_condition:b.information_condition,metric,output_status:status,output_source:source,output_source_sha256:source?provenance.source_sha256[source]:null,metric_source:b.metric_source,metric_source_sha256:provenance.source_sha256[`manuscript/notes/${b.metric_source}`],scorer:b.scorer,postprocessing:b.postprocessing,archive_hashes:b.archive_hashes,review:record?.review||null},null,2)));
    row.append(detail);$('baseline-rows').append(row);
  });
}

async function ensureAudio(autoplay) {
  if (!current) return;
  const token=++audioToken, snapshot=current, receiver=$('receiver').value;
  audioAbort?.abort();audioAbort=new AbortController(); player.pause();player.receiver=receiver;currentWave=[];drawWave(player.position);
  $('play').disabled=true;
  try {
    if (!player.buffers.has(receiver)) {
      $('audio-status').textContent=`Loading and verifying ${receiver} audio…`;
      const audio=snapshot.input.audio.find(a=>a.id===receiver);
      const [bytes,decoder]=await Promise.all([downloadAudio(provenance.audio_base+audio.path,audioAbort.signal,(loaded,total)=>{
        if(token===audioToken)$('audio-status').textContent=`Loading ${receiver} audio · ${Math.round(loaded/total*100)}%`;
      }),fetchJSON('assets/decoder.json')]);
      if(await sha256(bytes)!==audio.sha256)throw Error('Audio checksum mismatch.');
      const wav=parseWav(bytes), buffer=await decodeFOA(wav,decoder);
      if(token!==audioToken||snapshot!==current)return;
      player.buffers.set(receiver,buffer);
    }
    if(token!==audioToken||snapshot!==current)return;
    currentWave=waveform(player.buffers.get(receiver).getChannelData(0));drawWave(player.position);
    $('audio-status').textContent=`${receiver} ready · SHA-256 verified · binaural playback`;
    if(autoplay)await player.play();
  } catch(e) {if(token===audioToken&&e.name!=='AbortError')$('audio-status').textContent=`Playback unavailable: ${e.message} Use Listen to retry.`;}
  finally {if(token===audioToken){$('play').disabled=false;$('play').textContent=player.playing?'Ⅱ Pause':'▶ Listen';}}
}
$('play').onclick=async()=>{if(player.playing){player.pause();$('play').textContent='▶ Listen';}else{try{await player.context();await ensureAudio(true);}catch(e){$('audio-status').textContent=e.message;}}};
$('receiver').onchange=()=>{const resume=player.playing;ensureAudio(resume);draw(player.position);};
$('timeline').oninput=()=>player.seek(Number($('timeline').value));
$('volume').oninput=()=>player.setVolume(Number($('volume').value));

function contextFor(id) {const c=$(id),ctx=c.getContext('2d');const width=Math.round(c.clientWidth*2),height=Math.round(c.clientHeight*2);if(width&&height&&(c.width!==width||c.height!==height)){c.width=width;c.height=height;}ctx.clearRect(0,0,c.width,c.height);ctx.font='20px system-ui';ctx.lineWidth=2;ctx.textBaseline='middle';return [ctx,c.width,c.height];}
function label(ctx,text,x,y,color='#61736e',size=18){ctx.font=`${size}px system-ui`;ctx.fillStyle=color;ctx.fillText(text,x,y);}
function line(ctx,points,color,dashed=false){if(!points.length)return;ctx.strokeStyle=color;ctx.setLineDash(dashed?[7,6]:[]);ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);}
function dot(ctx,x,y,color,r=8,square=false){ctx.fillStyle=color;ctx.beginPath();if(square)ctx.rect(x-r,y-r,r*2,r*2);else ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();}
function draw(time) {if(!current)return;drawScene(time);drawTask(time);}
function drawScene(time) {
  const [ctx,w,h]=contextFor('scene-map'),{reference,gold,input}=current;
  const positions=reference.entities.flatMap(e=>e.positions.map(p=>[p[1],p[3]]));
  const region=input.query?.region;
  if(region)positions.push([region.min_xyz_m[0],region.min_xyz_m[2]],[region.max_xyz_m[0],region.max_xyz_m[2]]);
  const xs=positions.map(p=>p[0]),zs=positions.map(p=>p[1]),minX=Math.min(...xs)-1.8,maxX=Math.max(...xs)+1.8,minZ=Math.min(...zs)-1.8,maxZ=Math.max(...zs)+1.8;
  const scale=Math.min((w-110)/(maxX-minX),(h-100)/(maxZ-minZ)),px=x=>(w-(maxX-minX)*scale)/2+(x-minX)*scale,py=z=>(h-(maxZ-minZ)*scale)/2+(maxZ-z)*scale;
  ctx.lineWidth=1;for(let x=Math.ceil(minX);x<=maxX;x++){line(ctx,[[px(x),py(minZ)],[px(x),py(maxZ)]],'#e5ede6');if(x%2===0)label(ctx,`${x}`,px(x)-8,py(minZ)+24,'#82938b',16);}
  for(let z=Math.ceil(minZ);z<=maxZ;z++){line(ctx,[[px(minX),py(z)],[px(maxX),py(z)]],'#e5ede6');if(z%2===0)label(ctx,`${z}`,px(minX)-27,py(z),'#82938b',16);}
  label(ctx,'X →',w-65,h-18);label(ctx,'Z ↑',12,20);ctx.lineWidth=2;
  if(region){const a=region.min_xyz_m,b=region.max_xyz_m;ctx.fillStyle='#c56d3220';ctx.fillRect(px(a[0]),py(b[2]),(b[0]-a[0])*scale,(b[2]-a[2])*scale);line(ctx,[[px(a[0]),py(a[2])],[px(b[0]),py(a[2])],[px(b[0]),py(b[2])],[px(a[0]),py(b[2])],[px(a[0]),py(a[2])]],'#c56d32',true);label(ctx,'query region',px(a[0]),py(b[2])-15,'#c56d32',16);}
  if(input.query?.cue_type==='world_trajectory'){line(ctx,input.query.frames.map(f=>[px(f.xyz_m[0]),py(f.xyz_m[2])]),'#c56d32',true);label(ctx,'Dashed orange: query trajectory',45,25,'#c56d32',16);}
  for(const e of reference.entities){
    const receiver=e.id.startsWith('R'),target=e.id===gold.target_source_id,position=positionAt(e.positions,time);if(!position)continue;
    const active=reference.sources.some(s=>s.entity_id===e.id&&s.start<=time&&time<s.end),color=target?'#c56d32':receiver?'#3673bd':'#087f73';
    if(e.positions.length>1){ctx.globalAlpha=.3;line(ctx,e.positions.map(p=>[px(p[1]),py(p[3])]),color,true);ctx.globalAlpha=1;}
    const x=px(position[0]),y=py(position[2]);
    if(target||e.id===player.receiver){ctx.strokeStyle=color;ctx.beginPath();ctx.arc(x,y,18,0,Math.PI*2);ctx.stroke();}
    if(active){ctx.strokeStyle=color;ctx.globalAlpha=.25;ctx.lineWidth=5;ctx.beginPath();ctx.arc(x,y,25,0,Math.PI*2);ctx.stroke();ctx.globalAlpha=1;ctx.lineWidth=2;}
    dot(ctx,x,y,color,receiver?8:9,receiver);label(ctx,`${e.id}${target?' · target':''}`,x+15,y-14,color,19);
    if(receiver){const a=e.yaw*Math.PI/180;line(ctx,[[x,y],[x+Math.sin(a)*27,y+Math.cos(a)*27]],color);if(!input.receiver_ids.includes(e.id))label(ctx,'metadata only',x+15,y+10,'#82938b',14);}
  }
}
function drawTask(time) {
  const [ctx,w,h]=contextFor('task-map'),{q,gold,result}=current,task=q.task,grid=gold.expected_times_s||[];
  const series=[{name:'Reference',color:'#087f73',output:gold.output},...baselines.filter(b=>overlays.has(b.id)&&result.outputs[b.id]?.status==='available').map(b=>({name:b.name,color:colors[baselines.indexOf(b)],output:result.outputs[b.id].output}))];
  const points=series.map(s=>({...s,values:spatialValues(task,s.output,time,grid)}));
  const isDirection=['DOA','TEXT_DOA','DOA_TRAJECTORY'].includes(task),isDistance=['RANGE','TEXT_RANGE','RANGE_TRAJECTORY'].includes(task),isPosition=['C1_SETLOC','C3_TEXTLOC','TEXT_TRAJECTORY'].includes(task);
  $('task-plot-title').textContent=isDirection?'Direction · azimuth / elevation':isDistance?'Distance to receiver':isPosition?'Position · world X/Z':'Spatial cue & speech';
  $('plot-note').textContent=grid.length?'Reference and submitted frames on the 0.5 s evaluation grid. Missing or inactive predictions are not drawn. All numeric values remain available below.':'Green is the reference. Model colors match the overlay controls below. Full numeric answers are preserved.';
  if(isDirection){
    const cx=w/2,cy=h/2,r=Math.min(w,h)*.3;ctx.strokeStyle='#dce6df';ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.stroke();
    line(ctx,[[cx-r,cy],[cx+r,cy]],'#e0e8e2');line(ctx,[[cx,cy-r],[cx,cy+r]],'#e0e8e2');
    label(ctx,'front 0°',cx-42,cy-r-25);label(ctx,'+90° left',12,cy);label(ctx,'right −90°',w-105,cy);label(ctx,'back ±180°',cx-65,cy+r+30);
    for(const s of points)for(const p of s.values){const [az,el]=p.value;if(!Number.isFinite(az)||!Number.isFinite(el))continue;const a=az*Math.PI/180,x=cx-Math.sin(a)*r,y=cy-Math.cos(a)*r;line(ctx,[[cx,cy],[x,y]],s.color,s.name!=='Reference');dot(ctx,x,y,s.color,7);label(ctx,`${az.toFixed(1)}° / ${el.toFixed(1)}°`,Math.max(8,Math.min(w-160,x-50)),y+(y<cy?-17:22),s.color,16);}
    dot(ctx,cx,cy,'#17332f',6);
  }else if(isDistance){
    const vals=points.flatMap(s=>s.values.map(p=>p.value)).filter(Number.isFinite),max=Math.max(1,...vals)*1.15;
    if(!vals.length){label(ctx,'No active submitted frame at this time.',25,h/2);return;}
    let y=70;for(const s of points){for(const p of s.values){if(!Number.isFinite(p.value))continue;label(ctx,`${s.name} · ${p.value.toFixed(3)} m`,25,y,s.color,18);ctx.fillStyle=s.color;ctx.fillRect(25,y+16,(w-80)*p.value/max,10);y+=90;}}label(ctx,`Shared scale: 0 – ${max.toFixed(1)} m`,25,h-35);
  }else if(isPosition){
    const all=series.flatMap(s=>s.output?.frames?s.output.frames.filter(f=>f.active&&Array.isArray(f.xyz_m)).map(f=>f.xyz_m):spatialValues(task,s.output,time,grid).map(p=>p.value)).filter(v=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite));
    if(!all.length){label(ctx,'No active submitted frame at this time.',25,h/2);return;}
    const minX=Math.min(...all.map(p=>p[0]))-1,maxX=Math.max(...all.map(p=>p[0]))+1,minZ=Math.min(...all.map(p=>p[2]))-1,maxZ=Math.max(...all.map(p=>p[2]))+1,scale=Math.min((w-100)/(maxX-minX),(h-100)/(maxZ-minZ));
    const px=x=>50+(x-minX)*scale,py=z=>h-50-(z-minZ)*scale;
    line(ctx,[[50,30],[50,h-50],[w-25,h-50]],'#c7d9ce');label(ctx,'X (m) →',w-110,h-20);label(ctx,'Z (m) ↑',12,15);
    label(ctx,minX.toFixed(1),50,h-25,'#61736e',15);label(ctx,maxX.toFixed(1),px(maxX)-20,h-25,'#61736e',15);label(ctx,minZ.toFixed(1),5,py(minZ),'#61736e',15);label(ctx,maxZ.toFixed(1),5,py(maxZ),'#61736e',15);
    for(const s of points){
      // Recorded trajectory points only: no line through gaps or interpolated frames.
      for(const f of s.output?.frames||[])if(f.active&&Array.isArray(f.xyz_m)){ctx.globalAlpha=.25;dot(ctx,px(f.xyz_m[0]),py(f.xyz_m[2]),s.color,3);ctx.globalAlpha=1;}
      for(const p of s.values){if(!Array.isArray(p.value)||!p.value.every(Number.isFinite))continue;const [x,y,z]=p.value;dot(ctx,px(x),py(z),s.color,8,s.name!=='Reference');label(ctx,`[${x.toFixed(2)}, ${y.toFixed(2)}, ${z.toFixed(2)}]`,Math.max(8,Math.min(w-200,px(x)+12)),py(z)-18,s.color,15);}
    }
  }else{
    const empty=gold.output==='';label(ctx,empty?'No matching target':'Listen for the spatially cued speaker',25,70,'#17332f',22);
    label(ctx,empty?'Correct reference: empty transcript':'The transcript covers all target speech.',25,110,'#61736e',18);
    const target=gold.target_source_id,receiver=gold.reference_robot_id;
    label(ctx,`Reference target: ${target}`,25,180,'#087f73',20);if(receiver)label(ctx,`Listening perspective: ${receiver}`,25,220);
    label(ctx,'Read the allowed cue below.',25,300);label(ctx,'Compare full responses and WER.',25,335);
    $('plot-note').textContent='Target identity shown here is evaluator-only. The model receives the public spatial cue, not this identity or the reference transcript.';
  }
  if(!asrTasks.has(task)&&!points.some(s=>s.values.length))label(ctx,'No active submitted frame at this time.',25,h-25,'#a1653b',18);
}
function drawWave(time){const [ctx,w,h]=contextFor('waveform');ctx.strokeStyle='#a5c5b8';if(currentWave.length){const max=Math.max(.001,...currentWave);ctx.lineWidth=3;for(let i=0;i<currentWave.length;i++){const x=i*w/currentWave.length,v=currentWave[i]/max*(h/2-5);line(ctx,[[x,h/2-v],[x,h/2+v]],'#a5c5b8');}}else line(ctx,[[0,h/2],[w,h/2]],'#e0e8e2');if(current){line(ctx,[[w*time/current.scene.duration,0],[w*time/current.scene.duration,h]],'#087f73');}}

function table(headers,rows){const wrap=node('div',undefined,'table-scroll'),t=node('table'),thead=node('thead'),tr=node('tr');headers.forEach(h=>{const th=node('th',h);th.scope='col';tr.append(th);});thead.append(tr);const body=node('tbody');for(const row of rows){const r=node('tr');row.forEach(c=>r.append(node('td',String(c))));body.append(r);}t.append(thead,body);wrap.append(t);return wrap;}
function renderResults(results){
  for(const view of ['Egocentric','Allocentric']){
    const tasks=Object.entries(index.tasks).filter(([,v])=>v.view===view),overall=view.toLowerCase()+'_overall';
    $('result-tables').append(node('h3',view,'table-title'),table(['Model · input',...tasks.map(([id,t])=>`${t.code} ${asrTasks.has(id)?'WER ↓':'Acc ↑'}`),'Overall ↑'],baselines.map(b=>[`${b.name} · ${b.input}`,...tasks.map(([id])=>results[b.id][id].toFixed(2)),results[b.id][overall].toFixed(2)])));
  }
  $('result-tables').append(node('p','Overall: 50% localization and 50% semantics per view; questions have equal weight within each objective. Protocol: dish_case_equal_two_objectives_v1. Task accuracies use their frozen task-specific denominators, which need not equal per-question Overall components.','small'));
}
async function init(){
  try{
    [index,baselines,provenance]=await Promise.all(['index','baselines','provenance'].map(f=>fetchJSON(`data/${f}.json`)));
    questions=index.scenes.flatMap(s=>s.questions.map(q=>({...q,scene:s.id,room:s.room,base:s.base,mode:s.mode,humans:s.humans,receivers:s.receivers,snr:s.snr,motion:s.motion}))).sort((a,b)=>a.id.localeCompare(b.id));questionMap=new Map(questions.map(q=>[q.id,q]));
    for(const [id,t]of Object.entries(index.tasks)){const o=node('option',`${t.code} · ${t.name}`);o.value=id;$('task').append(o);}
    for(const example of index.defaults){const b=node('button',example.label);b.onclick=()=>{setTab('explore');selectQuestion(example.question);};$('defaults').append(b);}
    for(const id of index.archived_examples){const q=questionMap.get(id),o=node('option',`${index.tasks[q.task].code} · ${id.slice(0,10)}…`);o.value=id;$('diagnostics').append(o);}
    $('availability').textContent=`${provenance.metric_records.toLocaleString()} archived per-question scores cover all ${questions.length.toLocaleString()} questions and ${baselines.length} configurations. Actual raw/reviewed output records are currently available for ${provenance.output_records} model–question pairs across ${provenance.output_questions} questions. Full original prediction archives have not been recovered for this release.`;
    $('coverage-table').replaceChildren(table(['Configuration','Input','Scored questions','Archived outputs'],baselines.map(b=>[`${b.name} · ${b.id}`,b.input,b.metric_records.toLocaleString(),b.output_records])));
    const {source_sha256,shard_sha256,scene_asset_sha256,...binding}=provenance;$('provenance').textContent=JSON.stringify(binding,null,2);
    filterQuestions();$('global-status').hidden=true;
    await Promise.all([selectQuestion(new URLSearchParams(location.search).get('q')||index.defaults[0].question),fetchJSON('data/paper-results.json').then(renderResults)]);
  }catch(e){$('global-status').hidden=false;$('global-status').className='error';$('global-status').textContent=`Could not initialize the explorer: ${e.message} Reload to retry.`;}
}
init();
