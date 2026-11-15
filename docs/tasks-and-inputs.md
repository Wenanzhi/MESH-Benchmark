# Tasks and permitted inputs

MESH evaluates the association between speech content and spatial position
from different receiving perspectives, including persistence under source or
receiver motion. Egocentric questions use the focal receiver's recording and
permitted peer metadata. Allocentric questions use the synchronized recordings
of all receivers and their permitted metadata. In released JSON, the legacy
keys `edge` and `cloud` denote these views; they are not renamed in the protocol.

| Code | Task ID | Question / required output |
| --- | --- | --- |
| ES-Dir | `DOA` | Localize audible speech sources as azimuth/elevation pairs. |
| ES-Dist | `RANGE` | Estimate the microphone distance of the direction-cued source. |
| ES-CDir | `TEXT_DOA` | Locate the source of a supplied transcript as azimuth/elevation. |
| ES-CDist | `TEXT_RANGE` | Estimate the distance of the source of a supplied transcript. |
| ES-Trans | `DOA_RANGE_ASR` | Transcribe the speaker specified by a spatial cue. |
| AS-Pos | `C1_SETLOC` | Return the set of human-source positions in world XYZ. |
| AS-CPos | `C3_TEXTLOC` | Return the world position of the source of a supplied transcript. |
| AS-Trans | `C2_REGION_ASR` | Transcribe speech selected by a world-space region, including empty regions. |
| ED-Dir | `DOA_TRAJECTORY` | Track human-source direction and activity with stable track identities. |
| ED-Dist | `RANGE_TRAJECTORY` | Track the distance and activity of the cued source. |
| ED-Trans | `SPATIAL_ASR` | Transcribe the speaker selected by spatial and temporal anchors. |
| AD-CPos | `TEXT_TRAJECTORY` | Track the world position/activity of the source of a supplied transcript. |
| AD-Trans | `WORLD_TRAJECTORY_ASR` | Transcribe the speaker selected by a world trajectory. |

E/A denote Egocentric/Allocentric; S/D denote Static/Dynamic. Counts and exact
output schemas come from the pinned dataset, not these explanatory labels.
Static DOA can include other receivers' audible playback as specified by the
question; the human tracking tasks use their own explicit target definition.
Environmental noise is interference, not a recognition target.

Use the public loader to build prompts. Keep the full recording interval,
receiver labels, geometry and exact task query. Do not concatenate recordings
from different receivers along time or silently downmix FOA. The frozen
configurations are compared with their recorded input adapters:

| Input label | Meaning |
| --- | --- |
| FOA-W | Omnidirectional W channel only |
| FOA-sep | Four FOA channels supplied as separately labeled mono audio |
| Binaural | Model's frozen binaural rendering/adaptation |
| FOA | Native four-channel FOA input; MESH-agent uses its frozen acoustic tool chain |

The browser's FOA-to-binaural player is a listening aid, not a reconstruction of
every model's input adapter. Public metadata and query variants must be compared
only over their common eligible IDs. Refer to `public/ablation_recipes.json` and
`public/test/spatial_query_variants.jsonl` for the released alternatives.

Dynamic spatial answers use timestamps at 0.5-second intervals, strictly before
the clip ends. Preserve activity flags and missing frames. Spatial transcription
returns **all target speech in the input**, not only the anchor interval. An
explicit valid empty transcript, a refusal, a null answer and a missing request
have different evaluation meanings.
