import test from 'node:test';
import assert from 'node:assert/strict';
import {assertBinding, displayOutput, exactFrame, metricLabel, outputStatus, spatialValues} from '../data-utils.mjs';

test('an absent archive record is neither a valid empty answer nor a failed run', () => {
  assert.equal(outputStatus(undefined), 'missing_record');
  assert.equal(outputStatus({status:'valid_empty',output:''}), 'valid_empty');
  assert.equal(outputStatus({status:'invalid',output:null}), 'invalid');
  assert.notEqual(displayOutput(''), displayOutput(null));
});
test('uncapped WER and zero scores are displayed without filling missing metrics', () => {
  assert.equal(metricLabel({case_wer:2.5,case_score:0},'SPATIAL_ASR')[0], '250.00% WER');
  assert.equal(metricLabel({case_wer:null,case_score:0},'C2_REGION_ASR',true)[0], '0.00%');
  assert.equal(metricLabel(null,'DOA')[0], 'Metric not archived');
});
test('missing and inactive trajectory frames stay absent rather than interpolated', () => {
  const frames=[{time_s:0,active:true,distance_m:2},{time_s:1,active:false,distance_m:8},{time_s:1.5,active:true,distance_m:4}];
  assert.equal(exactFrame(frames,.5,[0,.5,1,1.5]), null);
  assert.deepEqual(spatialValues('RANGE_TRAJECTORY',{frames},.6,[0,.5,1,1.5]), []);
  assert.deepEqual(spatialValues('RANGE_TRAJECTORY',{frames},1,[0,.5,1,1.5]), []);
  assert.equal(spatialValues('RANGE_TRAJECTORY',{frames},1.5,[0,.5,1,1.5])[0].value,4);
});
test('submitted transcript repetitions and insertions are retained verbatim', () => {
  const text='Hello hello\n[noise] the the the. <script>alert(1)</script>';
  assert.equal(displayOutput(text),text);
});
test('question, task, scene and permitted receivers must all agree before display', () => {
  const q={id:'qid',task:'DOA',scene:'scene',setting:'edge'};
  const scene={id:'scene',questions:[{id:'qid',task:'DOA',setting:'edge',receiver_ids:['R01']}]};
  const ref={id:'scene',questions:{qid:{sample_id:'qid',task_id:'DOA',episode_id:'scene',setting:'edge'}}};
  const result={scene:'scene',task:'DOA',receivers:['R01']};
  assert.equal(assertBinding(q,scene,ref,result).input.receiver_ids.length,1);
  assert.throws(()=>assertBinding(q,scene,ref,{...result,receivers:['R02']}),/identity mismatch/);
  assert.throws(()=>assertBinding(q,scene,ref,{...result,task:'RANGE'}),/identity mismatch/);
  assert.throws(()=>assertBinding({...q,id:'other'},scene,ref,result),/identity mismatch/);
});
