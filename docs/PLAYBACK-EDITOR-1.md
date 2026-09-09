# Playback + Editor Contract 1

Status: Beadtrain 2 foundation  
Semantic score format: `esn/1`  
Playback binding format: `esn-playback/1`

## Separation of meaning from rendering

ESN-1 remains the semantic authority. A score says what source makes what gesture, when it occurs, how long it lasts, and whether it has pitch. Playback profiles only describe how a particular renderer should make that event audible.

A cat `meow` is therefore not semantically a triangle oscillator. The reference player may synthesize it that way without changing the ESN event identity. Another renderer may use a sample library, physical model, MIDI target, or recorded field sound.

## Playback registry

A playback document contains:

- `format`: exactly `esn-playback/1`;
- `sample_rate`: integer from 8000 through 96000;
- `seed`: integer used for deterministic stochastic rendering;
- `profiles`: non-empty array of source/gesture bindings.

Each profile names a semantic `source` and either an exact `gesture` or `*` fallback. Exact gesture bindings take precedence over wildcard bindings.
## Reference synthesis modes

The standard-library renderer defines three deterministic reference modes:

- `oscillator`: sine, triangle, square, or saw wave; pitched ESN events drive frequency and pitch curves are interpolated continuously;
- `noise`: seeded white or softened noise for broadband sources such as rain and hiss;
- `impulse`: seeded exponentially decaying noise for transients such as doors and drums.

Profiles may set `gain`, `attack`, `release`, and `base_hz`. Dynamics in the ESN event multiply profile gain. `base_hz` is used when an oscillator profile renders an event without explicit pitch.

For stochastic modes, each event receives a deterministic PRNG seed derived from SHA-256 of `playback seed + ":" + event id`. Given the same validated score and playback registry, the reference renderer must emit byte-identical mono 16-bit PCM WAV output.

## Editor mutation rules

The browser editor edits ordinary ESN-1 events rather than maintaining a second proprietary score model.

- horizontal dragging snaps onset to quarter beats;
- vertical dragging of pitched events snaps by semitone;
- manually retuning an event removes its existing pitch curve rather than silently warping it;
- `required` pitch sources always retain a pitch;
- `forbidden` pitch sources remain in unpitched lanes;
- new event IDs are unique within the score;
- inspector changes preserve source-specific gesture validity;
- exported JSON uses recursively sorted object keys and remains ESN-1 shaped.
## Browser preview

The browser uses Web Audio for immediate authoring feedback. It follows the same profile families and pitch semantics, but browser preview is not the deterministic conformance artifact because browser audio implementations and live scheduling vary by platform.

Deterministic conformance is the Python WAV renderer.

## Accessibility

The editor preserves source and gesture text alongside emoji. Pitch remains visible through vertical position and note labels rather than hue alone. Controls use native form elements and the score timeline has an accessible label.

## Beadtrain 2 boundary

This train makes ESN audible and authorable without changing ESN-1. It does not yet define real sample-pack distribution, MIDI/MusicXML interchange, undo history, multiselect, tempo maps, collaboration, plugin hosting, or a production DAW audio engine. Those capabilities can build on the semantic and playback boundaries established here.
