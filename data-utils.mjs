// Display helpers only. No inference, parsing repair or scoring happens here.
export const viewName = setting => setting === 'edge' ? 'Egocentric' : 'Allocentric';
export const asrTasks = new Set(['DOA_RANGE_ASR', 'C2_REGION_ASR', 'SPATIAL_ASR', 'WORLD_TRAJECTORY_ASR']);
export const statusLabels = {available:'Archived output', valid_empty:'Valid empty output', invalid:'Invalid format', missing_record:'Output not archived', not_run:'Not run', unsupported:'Unsupported'};
export const outputStatus = record => record?.status || 'missing_record';
export const displayOutput = output => output === '' ? '""  (empty transcript)' : typeof output === 'string' ? output : JSON.stringify(output, null, 2);
export function metricLabel(metric, task, empty = false) {
  if (!metric) return ['Metric not archived', ''];
  if (asrTasks.has(task) && !empty && metric.case_wer !== null)
    return [`${(metric.case_wer * 100).toFixed(2)}% WER`, 'Original per-question WER ↓'];
  return [`${(metric.case_score * 100).toFixed(2)}%`, empty ? 'Empty-region correctness ↑' : 'Successful targets / active frames ↑'];
}
// Snap to the required grid, then require an exact frame. Never interpolate or
// substitute another prediction when a submitted frame is absent.
export function exactFrame(frames, time, grid = []) {
  const t = grid.length ? grid.reduce((best, x) => Math.abs(x - time) < Math.abs(best - time) ? x : best, grid[0]) : Math.round(time * 2) / 2;
  return (frames || []).find(f => Math.abs(f.time_s - t) < 1e-6) || null;
}
export function spatialValues(task, output, time, grid = []) {
  if (output === null || output === undefined) return [];
  if (task === 'DOA_TRAJECTORY') return (output.tracks || []).flatMap(track => {
    const f = exactFrame(track.frames, time, grid);
    return f?.active && f.doa_deg ? [{value:f.doa_deg, id:track.track_id, frame:f.time_s}] : [];
  });
  if (task === 'RANGE_TRAJECTORY' || task === 'TEXT_TRAJECTORY') {
    const f = exactFrame(output.frames, time, grid), key = task === 'RANGE_TRAJECTORY' ? 'distance_m' : 'xyz_m';
    return f?.active && f[key] !== undefined ? [{value:f[key], frame:f.time_s}] : [];
  }
  if (asrTasks.has(task)) return [];
  return (task === 'DOA' || task === 'C1_SETLOC' ? output : [output]).map((value, i) => ({value, id:i}));
}
// Interpolation is used only for scene geometry, never for model predictions.
export function positionAt(positions, time) {
  if (!positions?.length) return null;
  if (time <= positions[0][0]) return positions[0].slice(1);
  for (let i = 1; i < positions.length; i++) if (positions[i][0] >= time) {
    const a = positions[i - 1], b = positions[i], f = (time - a[0]) / (b[0] - a[0] || 1);
    return a.slice(1).map((x,j) => x + f * (b[j + 1] - x));
  }
  return positions.at(-1).slice(1);
}
export function assertBinding(question, scene, reference, result) {
  if (scene.id !== question.scene || reference.id !== scene.id || result.scene !== scene.id || result.task !== question.task)
    throw Error('Scene or task identity mismatch. The record will not be displayed.');
  const input = scene.questions.find(q => q.id === question.id), gold = reference.questions[question.id];
  if (!input || !gold || input.task !== question.task || gold.sample_id !== question.id || gold.task_id !== question.task || gold.episode_id !== scene.id || input.setting !== question.setting || gold.setting !== question.setting || JSON.stringify(input.receiver_ids) !== JSON.stringify(result.receivers))
    throw Error('Question, reference or receiver identity mismatch.');
  return {input, gold};
}
