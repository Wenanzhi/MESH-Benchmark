# Browser playback assets

`../audio.js` is adapted from Wenanzhi/dish-listening-review at
`c18bd9515a430a79673a0fb3d0f982d7f3135001`, copyright (c) 2026 Wenanzhi.
The MIT license is retained in `listening-MIT.txt`. Listening-review coverage
tracking was removed; playback, FOA decoding and waveform helpers were retained.

`decoder.json` is copied unchanged from that application's `web/assets/decoder.json`.
Its FIR decoder derives from MIT KEMAR HRTF measurements by Bill Gardner and
Keith Martin (1994), described by Gardner and Martin, “HRTF measurements of a
KEMAR,” JASA 97, 3907–3908 (1995). Original terms and citation:
https://sound.media.mit.edu/resources/KEMAR.html

Original SOFA SHA-256:
`647cebf09bd0ed5fca359c071d888779325a5c3376669b120029df817e7ea2bd`.

These terms are separate from the Apache-2.0 license for MESH-authored code.
Speech, environmental recordings and their annotations retain component terms:
see `../../docs/licenses-and-attributions.md`. The browser loads pinned audio
on demand and does not redistribute the full recordings in this Git repository.
