# Emoji Sound Notation 🎼🐈🌧️

**Working project name.** The permanent product name is intentionally not frozen yet.

Emoji Sound Notation (ESN) is a source-aware visual language for music and sound. It can compose instruments, animal calls, weather, Foley, percussion, and other sound events in one structured score without forcing every sound to behave like a musical note.

The customer-facing workflow is simple:

> Open → understand → add → edit → preview → save/open → hand off.

The browser composer uses plain-language source names, explicit track and section structure, score/track musical context, chord authoring, a lightweight reference synth for timing/pitch preview, and direct project/CSV/MIDI export. ESN/1 files still open through deterministic migration into the ESN/2 score model.

## Start it

On Windows, double-click `START_ESN.cmd`.

Cross-platform:

```powershell
python launch_esn.py
```

The launcher serves the correct repository root on localhost and opens the product landing page. The score stays local unless you explicitly export it.

See [`docs/CONSUMER-AUDIT.md`](docs/CONSUMER-AUDIT.md) for the observed first-customer acceptance pass.

## Beadtrain 1 — Semantic foundation

- `esn/1` score semantics;
- `esn-registry/1` source/gesture registries;
- note and Hz pitch forms plus explicitly unpitched events;
- continuous pitch curves;
- deterministic validation/canonicalization;
- deterministic standalone SVG semantic-score rendering.

See [`docs/ESN-1.md`](docs/ESN-1.md).

## Beadtrain 2 — Playback and editor

- `esn-playback/1` keeps sound meaning separate from playback implementation;
- deterministic mono PCM WAV rendering;
- oscillator, seeded-noise, and impulse reference playback;
- dependency-free browser editing, dragging, previewing, deleting, and exporting;
- Web Audio for live sketch preview while Python WAV remains the deterministic conformance surface.

See [`docs/PLAYBACK-EDITOR-1.md`](docs/PLAYBACK-EDITOR-1.md).

## Beadtrain 3 — Canonical visual language

- `esn-visual/1` separates visual binding from sound semantics;
- seven in-house tintable SVG source glyphs;
- absolute pitch-class and relative scale-degree color modes;
- explicit chromatic fallback and unpitched colors;
- deterministic glyph sheets and visual SVG rendering;
- browser color-mode switching with redundant text/position cues.

See [`docs/VISUAL-1.md`](docs/VISUAL-1.md).

## Beadtrain 4 — Loss-aware interchange and customer workflow

- `esn-interchange/1` defines deterministic mapping into Standard MIDI Files;
- playable pitched/percussion sources become MIDI notes where the mapping is meaningful;
- every ESN event is also preserved as timed semantic cue metadata;
- unmapped animal/environment/Foley events remain cue-only rather than being dropped or assigned fake instruments;
- deterministic production cue-sheet CSV includes beats and real-time seconds;
- browser and Python MIDI exporters are byte-identical for the reference score;
- New/Open/Save project lifecycle, editable title/BPM, direct Cue sheet and MIDI buttons;
- local customer launcher and customer-facing landing page;
- consumer acceptance audit recorded in the repository.

See [`docs/INTERCHANGE-1.md`](docs/INTERCHANGE-1.md).

## Beadtrain 5 — Swappable sound realization

- `esn-sound-pack/1` binds semantic source/action pairs to local WAV assets without modifying `esn/1`;
- exact action bindings and source-wide `*` fallbacks are supported;
- missing or unusable sample assets fall back to the deterministic reference synth instead of losing the event;
- optional root-pitch and looping controls let samples follow pitched events or fill long environmental events;
- browser users can load a licensed pack folder or attach their own WAV to a source/action for the current session;
- pack creator/license/provenance are visible in the editor;
- Save/New/Open preserve the semantic score independently from realization choice;
- Python sample-backed rendering remains deterministic for offline conformance.

See [`docs/SOUND-PACK-1.md`](docs/SOUND-PACK-1.md).

## Beadtrain 6 — Score grammar and multi-track composition

- `esn/2` adds a real score hierarchy: score → tracks → sections → sound objects;
- musical context resolves from score defaults through track and section overrides;
- factory defaults are 96 BPM, 4/4, C major, and A4=432 Hz;
- sections keep one explicit semantic source and split into unassigned empty sections rather than inventing a new source;
- notes, unpitched/optional-pitch events, and first-class chords can coexist polyphonically;
- chord authoring supports inversions, close/open voicing, optional arpeggiation, and explosion into independent notes;
- ESN/1 projects migrate deterministically by semantic source while preserving event meaning and timing;
- playback, visual, cue, MIDI, and sound-pack layers consume ESN/2 through a flattening adapter instead of owning the score grammar;
- the browser is now a multi-track composer with track/section controls, chord creation/explosion, Save/New/Open, preview, and export;
- [`examples/cat-counterpoint.esn.json`](examples/cat-counterpoint.esn.json) is the cat-heavy executable qualification score.

See [`docs/ESN-2.md`](docs/ESN-2.md) and the Train 6 section of [`docs/CONSUMER-AUDIT.md`](docs/CONSUMER-AUDIT.md).

## CLI / conformance tools

Python 3.11+ is sufficient; the core has no runtime dependencies.

```powershell
python -m pip install -e .
esn validate examples/first-score.esn.json --registry registries/core.json
esn visual-validate --visual visual/core.json --registry registries/core.json
esn interchange-validate --interchange interchange/core.json --registry registries/core.json
esn sound-pack-validate --sound-pack soundpacks/reference.json --registry registries/core.json
esn render examples/first-score.esn.json --registry registries/core.json --visual visual/core.json --color-mode pitch_class -o examples/first-score.svg
esn audio examples/first-score.esn.json --registry registries/core.json --playback playback/core.json -o examples/first-score.wav
esn audio examples/first-score.esn.json --registry registries/core.json --playback playback/core.json --sound-pack path/to/pack.json -o sample-backed.wav
esn midi-export examples/first-score.esn.json --registry registries/core.json --interchange interchange/core.json -o examples/first-score.mid --report examples/first-score-midi-report.json
esn cue-export examples/first-score.esn.json --registry registries/core.json --interchange interchange/core.json -o examples/first-score-cues.csv
```

Run `python -m unittest discover -s tests -v` and `node --test tests/web_domain.test.js` for the executable regression suites.

## Semantic event

```json
{"id":"cat-meow","source":"animal:cat","gesture":"meow","onset":1,"duration":1.5,"pitch":{"note":"E4"},"dynamics":0.82}
```

The semantic registry decides what the event means. Playback decides how the reference renderer makes it audible. The visual profile decides which portable glyph/color represents it. The interchange profile decides what can become MIDI directly and what must remain a timed semantic cue.

None of those binding layers changes the underlying ESN event identity.

The reference synth remains the built-in sketching fallback. Sound packs and local WAV overrides can now improve or stylize realization without rewriting ESN semantics.
