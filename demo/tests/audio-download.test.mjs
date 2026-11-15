import test from 'node:test';
import assert from 'node:assert/strict';
import {downloadAudio} from '../audio-download.mjs';

test('assemble exact audio bytes and retry a truncated range',async()=>{
  const original=new Uint8Array(2*1024*1024+73).map((_,i)=>i%251),attempts=new Map();
  const fetcher=async(url,options)=>{
    const [,startText,endText]=/bytes=(\d+)-(\d+)/.exec(options.headers.Range),start=Number(startText),end=Math.min(Number(endText),original.length-1);
    attempts.set(start,(attempts.get(start)||0)+1);
    const bytes=original.slice(start,end+1);
    return new Response(start===1048576&&attempts.get(start)===1?bytes.slice(0,10):bytes,{status:206,headers:{'Content-Range':`bytes ${start}-${end}/${original.length}`}});
  };
  assert.deepEqual(new Uint8Array(await downloadAudio('fixture',undefined,()=>{},fetcher)),original);
  assert.equal(attempts.get(1048576),2);
});
test('reject repeated wrong-range responses and honor cancellation',async()=>{
  const wrong=async()=>new Response(new Uint8Array(4),{status:206,headers:{'Content-Range':'bytes 10-13/20'}});
  await assert.rejects(downloadAudio('fixture',undefined,()=>{},wrong),/wrong range/);
  const c=new AbortController();c.abort();
  await assert.rejects(downloadAudio('fixture',c.signal,()=>{},wrong),{name:'AbortError'});
});
