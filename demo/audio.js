/* Adapted from Wenanzhi/dish-listening-review c18bd9515a430a79673a0fb3d0f982d7f3135001.
 * Copyright (c) 2026 Wenanzhi. MIT license; see assets/listening-MIT.txt.
 * Changes: remove listening-review coverage tracking; retain playback only. */
export function parseWav(arrayBuffer) {
  const v = new DataView(arrayBuffer);
  const str = (p, n) =>
    Array.from({ length: n }, (_, i) =>
      String.fromCharCode(v.getUint8(p + i)),
    ).join("");
  if (v.byteLength < 44 || str(0, 4) !== "RIFF" || str(8, 4) !== "WAVE")
    throw Error("Unsupported WAV file.");
  let format, channels, rate, bits, offset, bytes, align;
  for (let p = 12; p + 8 <= v.byteLength; ) {
    const id = str(p, 4),
      size = v.getUint32(p + 4, true),
      start = p + 8;
    if (start + size > v.byteLength) throw Error("Incomplete WAV file.");
    if (id === "fmt ") {
      format = v.getUint16(start, true);
      channels = v.getUint16(start + 2, true);
      rate = v.getUint32(start + 4, true);
      align = v.getUint16(start + 12, true);
      bits = v.getUint16(start + 14, true);
      if (format === 65534 && size >= 40)
        format = v.getUint16(start + 24, true);
    }
    if (id === "data") {
      offset = start;
      bytes = size;
    }
    p = start + size + (size % 2);
  }
  if (
    !offset ||
    channels !== 4 ||
    rate !== 16000 ||
    !((format === 3 && bits === 32) || (format === 1 && bits === 16)) ||
    align !== (channels * bits) / 8 ||
    bytes % align
  )
    throw Error("Expected a 16 kHz, four-channel ACN/SN3D FLOAT32 or PCM16 WAV.");
  const n = bytes / align,
    data = Array.from({ length: 4 }, () => new Float32Array(n));
  for (let i = 0; i < n; i++)
    for (let c = 0; c < 4; c++) {
      const p = offset + ((i * 4 + c) * bits) / 8;
      const x =
        format === 3 ? v.getFloat32(p, true) : v.getInt16(p, true) / 32768;
      if (!Number.isFinite(x)) throw Error("WAV contains non-finite samples.");
      data[c][i] = x;
    }
  return { rate, data, length: n };
}
export async function sha256(bytes) {
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
}
export async function decodeFOA(wav, decoder) {
  if (decoder.rate !== wav.rate) throw Error("Decoder sample rate does not match.");
  const context = new OfflineAudioContext(
    2,
    wav.length + decoder.filters[0][0].length - 1,
    wav.rate,
  );
  const split = context.createChannelSplitter(4),
    merge = context.createChannelMerger(2);
  const source = context.createBufferSource(),
    buffer = context.createBuffer(4, wav.length, wav.rate);
  wav.data.forEach((x, i) => buffer.copyToChannel(x, i));
  source.buffer = buffer;
  source.connect(split);
  for (let e = 0; e < 2; e++)
    for (let c = 0; c < 4; c++) {
      const conv = context.createConvolver();
      conv.normalize = false;
      const fir = context.createBuffer(
        1,
        decoder.filters[e][c].length,
        wav.rate,
      );
      fir.copyToChannel(new Float32Array(decoder.filters[e][c]), 0);
      conv.buffer = fir;
      split.connect(conv, c);
      conv.connect(merge, 0, e);
    }
  merge.connect(context.destination);
  source.start();
  return context.startRendering();
}
export function encodeStereoWav(buffer, gain = 1) {
  if (buffer.numberOfChannels !== 2 || !Number.isFinite(gain) || gain <= 0)
    throw Error("A binaural signal and a valid playback gain are required.");
  const bytes = new ArrayBuffer(44 + buffer.length * 4);
  const view = new DataView(bytes);
  const write = (offset, text) =>
    [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  write(0, "RIFF");
  view.setUint32(4, bytes.byteLength - 8, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 2, true);
  view.setUint32(24, buffer.sampleRate, true);
  view.setUint32(28, buffer.sampleRate * 4, true);
  view.setUint16(32, 4, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, buffer.length * 4, true);
  for (let c = 0; c < 2; c++) {
    const samples = buffer.getChannelData(c);
    for (let i = 0; i < buffer.length; i++) {
      const x = samples[i] * gain;
      if (!Number.isFinite(x) || Math.abs(x) > 1)
        throw Error("The binaural signal exceeds the output range. Lower the volume before downloading.");
      view.setInt16(44 + (i * 2 + c) * 2,
        Math.round(x * (x < 0 ? 32768 : 32767)), true);
    }
  }
  return bytes;
}
export function waveform(data, bins = 180) {
  const out = [];
  for (let b = 0; b < bins; b++) {
    let p = 0;
    for (
      let i = Math.floor((b * data.length) / bins);
      i < Math.floor(((b + 1) * data.length) / bins);
      i++
    )
      p = Math.max(p, Math.abs(data[i]));
    out.push(p);
  }
  return out;
}
export class Player {
  constructor(onTime) {
    this.onTime = onTime;
    this.buffers = new Map();
    this.position = 0;
    this.playing = false;
    this.receiver = null;
    this.gain = 0.7;
    this.timer = setInterval(() => this.tick(), 60);
  }
  async context() {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.volume = this.ctx.createGain();
      this.volume.gain.value = this.gain;
      this.volume.connect(this.ctx.destination);
    }
    await this.ctx.resume();
    return this.ctx;
  }
  reset() {
    this.pause();
    this.buffers.clear();
    this.position = 0;
    this.receiver = null;
  }
  async play() {
    await this.context();
    if (!this.receiver || !this.buffers.has(this.receiver)) return;
    this.pause();
    if (this.position >= this.duration) this.position = 0;
    const src = this.ctx.createBufferSource();
    src.buffer = this.buffers.get(this.receiver);
    src.connect(this.volume);
    src.start(0, this.position);
    this.source = src;
    this.started = this.ctx.currentTime;
    this.offset = this.position;
    this.playing = true;
    src.onended = () => {
      if (this.source === src && this.playing) {
        this.tick();
        this.pause();
        this.position = this.duration;
        this.onTime(this.position);
      }
    };
  }
  pause() {
    if (this.playing) {
      this.tick();
      this.playing = false;
      this.source?.stop();
      this.source = null;
    }
  }
  seek(t) {
    const playing = this.playing;
    this.pause();
    this.position = Math.max(0, Math.min(this.duration || 0, t));
    this.onTime(this.position);
    if (playing) this.play();
  }
  switch(id) {
    const playing = this.playing;
    this.pause();
    this.receiver = id;
    if (playing) this.play();
  }
  tick() {
    if (!this.playing) return;
    this.position = Math.min(
      this.duration,
      this.offset + this.ctx.currentTime - this.started,
    );
    this.onTime(this.position);
  }
  setVolume(v) {
    this.gain = v;
    if (this.volume) this.volume.gain.value = v;
  }
}
