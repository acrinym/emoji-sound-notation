# Consumer Audit

Status: Beadtrain 4
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
