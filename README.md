# Emoji Sound Notation 🎼🐈🌧️

**Working project name.** The permanent product name is intentionally not frozen yet.

Emoji Sound Notation (ESN) is a semantic visual language for music and sound. Sources identify what makes a sound, source-specific gestures identify what sound action occurs, X position represents time, Y position represents pitch when pitch exists, geometry represents duration/dynamics/trajectory, and color redundantly encodes pitch through a selected visual profile.

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
- Web Audio provides live authoring preview while Python WAV rendering remains the deterministic conformance surface.

See [`docs/PLAYBACK-EDITOR-1.md`](docs/PLAYBACK-EDITOR-1.md).

## Beadtrain 3

Beadtrain 3 adds a portable canonical visual binding without changing ESN-1 semantics:

- `esn-visual/1` separates visual renderer choices from semantic source identity;
- seven in-house SVG source glyphs replace vendor emoji artwork when the canonical visual profile is selected;
- every canonical glyph is truly tintable into arbitrary pitch colorways;
- `pitch_class` mode assigns one of 12 absolute colors;
- `scale_degree` mode colors notes relative to a configurable tonic and scale interval set;
- out-of-scale notes use an explicit chromatic fallback instead of pretending to be scale degrees;
- unpitched events use an explicit unpitched color and stay in spectral lanes;
- the browser editor switches visual modes live while preserving textual and positional accessibility cues.

See [`docs/VISUAL-1.md`](docs/VISUAL-1.md).

## Run it

Python 3.11+ is sufficient; the core has no runtime dependencies.

```powershell
python -m pip install -e .
esn validate examples/first-score.esn.json --registry registries/core.json
esn visual-validate --visual visual/core.json --registry registries/core.json
esn render examples/first-score.esn.json --registry registries/core.json --visual visual/core.json --color-mode pitch_class -o examples/first-score.svg
esn render examples/first-score.esn.json --registry registries/core.json --visual visual/core.json --color-mode scale_degree -o examples/first-score-degree.svg
esn glyph-sheet --registry registries/core.json --visual visual/core.json -o examples/core-glyph-colorways.svg
esn audio examples/first-score.esn.json --registry registries/core.json --playback playback/core.json -o examples/first-score.wav
```

Run `python -m unittest discover -s tests -v` and `node --test tests/web_domain.test.js` for the executable regression suites.

Serve the repository root with `python -m http.server 8000`, then open `/web/` for the score editor.

Color is always redundant. Pitch remains recoverable through vertical position and text/accessibility descriptions, and source identity remains recoverable through source/gesture text even when custom glyphs are used.

## Semantic event

```json
{"id":"cat-meow","source":"animal:cat","gesture":"meow","onset":1,"duration":1.5,"pitch":{"note":"E4"},"dynamics":0.82}
```

The semantic registry decides that `animal:cat` means a cat source and which gestures are lawful. The playback registry decides how a renderer makes that event audible. The visual profile decides which portable canonical glyph and redundant pitch color represent it. None of those binding layers changes the underlying ESN event identity.
