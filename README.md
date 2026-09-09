# Emoji Sound Notation 🎼🐈🌧️

**Working project name.** The permanent product name is intentionally not frozen in Beadtrain 1.

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
## Run it

Python 3.11+ is sufficient; the core has no runtime dependencies.

```powershell
python -m pip install -e .
esn validate examples/first-score.esn.json --registry registries/core.json
esn canonicalize examples/first-score.esn.json --registry registries/core.json -o examples/first-score.canonical.json
esn render examples/first-score.esn.json --registry registries/core.json -o examples/first-score.svg
python -m unittest discover -s tests -v
```

The renderer uses color as redundant pitch-class information. Pitch remains recoverable through vertical position and text/accessibility descriptions.

## Semantic event

```json
{"id":"cat-meow","source":"animal:cat","gesture":"meow","onset":1,"duration":1.5,"pitch":{"note":"E4"},"dynamics":0.82}
```

The registry decides that `animal:cat` renders as 🐈 and which gestures are lawful for that source. A source may require pitch, allow pitch, or forbid pitch.
