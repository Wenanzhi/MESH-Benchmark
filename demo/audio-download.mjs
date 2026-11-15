// Bound requests so a dropped large transfer can be retried without starting
// the whole recording again. The caller verifies the assembled SHA-256.
export async function downloadAudio(url, signal, onProgress = () => {}, fetcher = fetch) {
  const chunkSize = 1024 * 1024;
  async function part(start, end) {
    let lastError;
    for (let attempt = 0; attempt < 3; attempt++) {
      signal?.throwIfAborted();
      try {
        const signals = [AbortSignal.timeout(60000)]; if (signal) signals.push(signal);
        const response = await fetcher(url, {headers:{Range:`bytes=${start}-${end}`},signal:AbortSignal.any(signals)});
        if (!response.ok) throw Error(`Audio server returned HTTP ${response.status}.`);
        const bytes = new Uint8Array(await response.arrayBuffer());
        if (response.status === 200 && start === 0) return {bytes, total:bytes.length, full:true};
        const match = /^bytes (\d+)-(\d+)\/(\d+)$/.exec(response.headers.get('Content-Range') || '');
        if (response.status !== 206 || !match) throw Error('Audio server did not return a valid byte range.');
        const [, a, b, total] = match.map(Number);
        if (a !== start || b !== Math.min(end,total-1) || bytes.length !== b-a+1 || total <= b)
          throw Error('Audio transfer was incomplete or returned the wrong range.');
        return {bytes,total};
      } catch (error) { signal?.throwIfAborted(); lastError=error; }
    }
    throw lastError;
  }
  const first = await part(0,chunkSize-1);
  if (first.full) {onProgress(first.total,first.total);return first.bytes.buffer;}
  if (first.total > 64 * 1024 * 1024) throw Error('Recording exceeds the supported browser buffer size.');
  const output = new Uint8Array(first.total);output.set(first.bytes);let loaded=first.bytes.length;
  onProgress(loaded,first.total);
  const starts=[];for(let start=chunkSize;start<first.total;start+=chunkSize)starts.push(start);
  // At most three concurrent transfers for one receiver.
  await Promise.all(Array.from({length:Math.min(3,starts.length)},async()=>{
    while(starts.length){const start=starts.shift(),chunk=await part(start,Math.min(start+chunkSize-1,first.total-1));
      if(chunk.total!==first.total)throw Error('Recording size changed during download.');
      output.set(chunk.bytes,start);loaded+=chunk.bytes.length;onProgress(loaded,first.total);
    }
  }));
  return output.buffer;
}
