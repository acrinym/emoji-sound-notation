# Emoji Sound Notation 🎼🐈🌧️

**Working project name.** The permanent product name is intentionally not frozen yet.

Emoji Sound Notation (ESN) is a semantic visual language for music and sound. Emoji identify sound sources, source-specific gestures identify what sound they make, X position represents time, Y position represents pitch when pitch exists, geometry represents duration/dynamics/trajectory, and color redundantly represents pitch class.

This is not conventional sheet music decorated with emoji. Unpitched sound is first-class, so rain, hisses, door slams, Foley, machinery, and environmental sound do not need invented notes.

## Beadtrain 1

The first product train establishes ESN-1 as an executable vertical slice:

- `esn/1` score semantics;
- `esn-registry/1` source/gesture registries;
- note and Hz pitch forms;
- explicitly unpitched events;
- continuous pitch curves;
- deterministic validator and canonicalizer;
- deterministic standalone SVG semantic-score rendering;
- mixed reference score covering music, animal vocalization, environment, Foley, and percussion.

See [`docs/ESN-1.md`](docs/ESN-1.md).

## Beadtrain 2

Beadtrain 2 makes the same semantic score audible and authorable without changing ESN-1:

- `esn-playback/1` keeps synthesis and playback choices separate from sound meaning;
- deterministic mono PCM WAV rendering covers oscillator, seeded noise, and impulse sources;
- pitch curves and event dynamics drive playback;
- the dependency-free browser editor adds, drags, edits, previews, deletes, and exports ESN events;
- forbidden-pitch sources remain in explicit unpitched lanes;
- Web Audio provides live authoring preview while Python WAV rendering remains the deterministic conformance surface.

See [`docs/PLAYBACK-EDITOR-1.md`](docs/PLAYBACK-EDITOR-1.md).

## Run it

Python 3.11+ is sufficient; the core has no runtime dependencies.

```powershell
python -m pip install -e .
esn validate examples/first-score.esn.json --registry registries/core.json
esn canonicalize examples/first-score.esn.json --registry registries/core.json -o examples/first-score.canonical.json
esn render examples/first-score.esn.json --registry registries/core.json -o examples/first-score.svg
esn audio examples/first-score.esn.json --registry registries/core.json --playback playback/core.json -o examples/first-score.wav
python -m unittest discover -s tests -v
```

Serve the repository root with `python -m http.server 8000`, then open `/web/` for the score editor.

The SVG renderer uses color as redundant pitch-class information. Pitch remains recoverable through vertical position and text/accessibility descriptions.

## Semantic event

```json
{"id":"cat-meow","source":"animal:cat","gesture":"meow","onset":1,"duration":1.5,"pitch":{"note":"E4"},"dynamics":0.82}
```

The semantic registry decides that `animal:cat` renders as 🐈 and which gestures are lawful for that source. The separate playback registry decides how a selected renderer makes that semantic event audible.
