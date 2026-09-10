# Consumer Audit

Status: Beadtrain 5
Date: 2026-09-09

## Question

What should a first-time customer see and be able to do with Emoji Sound Notation?

The customer contract used for this audit is:

> Open → understand → add → edit → preview → save/open → hand off.

The product should read as a visual sound-scene tool, not as a repository demo or schema debugger.

## Method

The actual checkout at `D:\github\emoji-sound-notation` was served locally and driven through Microsoft Edge with Playwright. Tests clicked the real controls, edited events, started Web Audio, downloaded ESN/CSV/MIDI files, reopened saved projects, changed tempo, and captured screenshots. MIDI was independently parsed with Mido.

No customer result below is inferred from source inspection alone.

## Baseline audit

| Journey | Expected | Actual | Result |
| --- | --- | --- | --- |
| Open `/` | Product introduction | Raw repository directory listing | FAIL |
| Open editor | Plain-language purpose and obvious first action | Developer-facing Beadtrain/binding language | FAIL |
| Add Cat → Meow | Add and select one sound | 6 → 7 events; selected correctly | PASS |
| Edit sound | Immediate timing/pitch update | Beat and pitch changed correctly | PASS |
| Play scene | Clean audible preview | AudioContext ran, but favicon 404 polluted console | FAIL |
| Change color meaning | Alternate visual semantics | Worked correctly | PASS |
| Save project | Editable project download | Valid ESN downloaded | PASS |
| Cue sheet | Production-friendly timecoded handoff | CSV covered every event | PASS |
| Discover MIDI | Visible DAW handoff | Feature existed only below the UI | FAIL |
| Clean browser | No console errors | `/favicon.ico` 404 | FAIL |

The baseline editor also exposed internal identifiers such as `instrument:piano`, `animal:cat`, and `foley:door`. Those identifiers remain useful in the file format, but they are not appropriate primary customer labels.

## Repairs made from the audit

- added a customer-facing root landing page instead of a directory listing;
- added a favicon and eliminated the browser 404;
- replaced internal source IDs with Piano, Bell, Cat, Wolf, Rain, Door, and Drum labels;
- replaced Gesture/Onset/Duration/Dynamics wording with Action/Starts at beat/Length/Loudness;
- added an explicit Start here card and plain-language color descriptions;
- exposed Cue sheet and standards-readable MIDI as direct browser actions;
- made browser MIDI byte-identical to the Python conformance exporter;
- added a local launcher (`START_ESN.cmd` / `launch_esn.py`);
- added New and Open project workflows;
- added editable scene title and BPM;
- changed playback language to honestly describe a lightweight reference-synth preview;
- moved internal event IDs under Advanced;
- added responsive header behavior for ordinary laptop widths.

## Re-audit: core customer journey

The first repaired pass completed 10/10 journeys successfully: landing, understanding the editor, adding, editing, previewing, changing color meaning, saving, cue-sheet export, MIDI export, and a zero-error browser session.

The edited seven-event MIDI file independently parsed as Standard MIDI File Type 1 at 480 ticks per quarter, with 3 playable notes and 7 timed ESN cue markers.

## Re-audit: project lifecycle

A second pass specifically attacked the missing project lifecycle.
| Journey | Expected | Actual | Result |
| --- | --- | --- | --- |
| Edit scene settings | Customer can name and tempo a scene | `Cat & Rain Sketch`, 80 BPM | PASS |
| Author change | Add and edit before saving | 6 → 7 events, new Meow at A4 | PASS |
| Save | Preserve title, tempo, events | Title, 80 BPM, 7 events persisted | PASS |
| New | Start clean without deleting demo events | Untitled, 120 BPM, 0 events | PASS |
| Open | Save → New → Open restores project | Title, tempo, and 7 events restored | PASS |
| Tempo/timecodes | Beat 2.5 at 80 BPM | 1.875000 s | PASS |
| Re-time | Beat 2.5 at 120 BPM | 1.250000 s | PASS |
| Invalid file | Explain failure without replacing scene | Rejected `format: nope`; current scene preserved | PASS |
| Preview promise | Make reference quality explicit | `Previewing 7 sounds with the reference synth.` | PASS |
| Clean session | No console errors | `[]` | PASS |

## Interchange receipts

For the bundled six-event reference score, both browser and Python MIDI exporters produce the same 1,112-byte payload:

`356D77D2EAE8DEDE53CCD18AAC8FBF337975665019CBB9E828F2347EC9BFCC14`

The export contains 3 playable MIDI notes and preserves all 6 ESN events as timed cue metadata. Unmapped animal/environment/Foley events are cue-only rather than silently discarded or assigned arbitrary instruments.

Cue-sheet timing is derived from the editable scene tempo, not a UI-only setting.

## Current customer promise

The reference synth is a sketching aid for timing and pitch. It is not a realistic sample library. A future sound-pack layer may provide recorded or richer synthesized source sounds without changing ESN event identity.

The current useful promise is:

> Build a mixed musical/non-musical sound scene, preview its structure, save and reopen it, and hand it off without losing the sounds that ordinary MIDI cannot represent directly.

## Post-qualification MIDI overlap repair

An adversarial review found that overlapping events mapped to the same MIDI channel and note could be truncated by the earlier event's note-off. The semantic cue survived, but the playable projection did not preserve the later event's declared duration.

The exporter now plans note lifetimes before writing. Program-backed pitched mappings spill colliding notes onto deterministic auxiliary channels with the same program, preserving both start and end ticks. If no semantically safe channel exists, the later event stays cue-only instead of claiming incorrect playable timing. Python and browser exporters share the same rule and a parsed-SMF regression proves the two-event overlap case.

## Beadtrain 5 re-audit — sound-pack realization

Train 5 was exercised again through the actual local product in Microsoft Edge using Playwright against `launch_esn.py`. The qualification pack was generated locally for the run and contained one valid PCM WAV binding (`Cat / Meow`) plus one deliberately missing binding (`Door / Slam`). It was not added to the repository as product content.

The realization contract under test was:

> Keep the ESN event semantic identity stable while allowing playback realization to change independently.

| Journey | Expected | Actual | Result |
| --- | --- | --- | --- |
| Open product | Existing landing/editor still works | Landing → canvas, 6 events | PASS |
| Default realization | Product starts without third-party samples | Reference Synth pack visible | PASS |
| Load pack folder | Discover manifest + assets locally | Audit Sample Pack loaded | PASS |
| Pack availability | Missing assets are explicit | 1/2 available, 1 fallback | PASS |
| Provenance | Creator/license visible | Creator + CC0 metadata shown | PASS |
| Cat / Meow | Exact semantic binding selects WAV | Pack WAV selected | PASS |
| Preview pack sample | WAV decodes and plays through Web Audio | Sample-backed preview | PASS |
| Door / Slam | Missing sample does not break event | Reference-synth fallback shown and played | PASS |
| Local WAV override | User can override source/action locally | Local WAV became active realization | PASS |
| Root pitch + loop | Local controls persist | C4 root + loop retained | PASS |
| Save project | Realization does not contaminate `esn/1` | Saved JSON contains semantic score only | PASS |
| New → Open | Score lifecycle remains independent | Pack and local realization state stayed separate | PASS |
| Clear local override | Return to pack binding | Pack sample restored | PASS |
| Reference Synth | Explicitly return to built-in fallback | Reference realization restored | PASS |
| Responsive 1440 | No page-level overflow | 1440/1440 | PASS |
| Responsive 1280 | No page-level overflow | 1280/1280 | PASS |
| Responsive 1024 | No page-level overflow | 1024/1024 | PASS |
| Browser health | No runtime noise | 0 console errors, 0 page errors, 0 failed requests | PASS |

The full automated Edge journey recorded **28/28 assertions green**.

### Interaction defect found during Train 5 qualification

The first Edge run exposed a real pre-existing interaction defect that unit/static tests had not caught: clicking a timeline event could fail to select it because the drag `pointerup` handler rebuilt the timeline before the browser dispatched the subsequent `click`. The rebuilt blank timeline then consumed the click and cleared selection.

The repair separates click from drag:

- movement must cross a small threshold before the interaction is treated as a drag;
- a simple click no longer rebuilds the timeline during `pointerup`;
- the blank-timeline click handler is assigned once instead of accumulating `once` listeners on every render;
- completed drags preserve the event selection while suppressing only the immediate synthetic blank-timeline click.

The Edge re-run after that repair passed event selection, pack realization selection, and the complete 28-assertion customer journey.

## Train 5 customer promise

The product can now say:

> Build a mixed musical/non-musical sound scene, choose how its semantic sounds are realized locally, preview it, save/reopen the semantic project, and hand it off without tying the score to one sample library.

The repository intentionally does not bundle third-party recordings. The built-in Reference Synth remains a deterministic fallback, while customers may load licensed sound-pack folders or their own WAV files locally.
