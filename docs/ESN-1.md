# ESN-1 — Emoji Sound Notation Semantic Contract

Status: Beadtrain 1 foundation
Format identifiers: `esn/1` and `esn-registry/1`

## 1. Purpose

ESN is a semantic visual language for sound. It is not conventional staff notation with emoji decoration. A score describes sound-producing sources and their gestures, places them in time, and optionally locates pitched sounds by musical note or frequency.

The core event relationship is:

`source + gesture + onset + duration + optional pitch + dynamics + articulation`

Examples:

- `animal:cat + meow + E4` means a cat vocalization with pitch semantics.
- `animal:cat + hiss` may remain unpitched.
- `nature:rain + fall` is explicitly unpitched.
- `instrument:piano + strike + C4` requires pitch.

## 2. Coordinate model

The canonical visual interpretation uses X for time and Y for pitch. Pitched events occupy the pitch field. Events without pitch occupy explicit unpitched/spectral lanes rather than receiving invented notes.

Color is redundant pitch encoding, never the sole carrier of pitch identity. Renderers must preserve a non-color cue such as vertical position, note/frequency label, pattern, or accessible description.

## 3. Source registry

A source registry separates semantic identity from platform emoji rendering. Each source defines:

- `id`: stable namespaced identity such as `animal:cat`;
- `glyph`: default emoji/pictographic representation;
- `class`: broad source family;
- `pitch_policy`: `required`, `optional`, or `forbidden`;
- `gestures`: valid source-specific sound actions.

A gesture answers **what sound action the source is performing**. `meow`, `purr`, `hiss`, `slam`, `ring`, and `fall` are gesture semantics. The glyph answers **what kind of thing is producing or representing the sound**.

Registry lookup is part of validation. A score cannot silently invent an unknown source or gesture.

## 4. Event fields

Required event fields are `id`, `source`, `gesture`, `onset`, and `duration`.

- `onset` and `duration` are measured in beats for ESN-1.
- `dynamics` is optional and ranges from 0.0 through 1.0; default is 0.75.
- `articulation` is optional: `normal`, `staccato`, `tenuto`, `accent`, or `legato`.
- `pitch` is optional at the format level but constrained by the source's pitch policy.
- `pitch_curve` is optional and defines a continuous semantic trajectory through normalized event time.

## 5. Pitch

A pitch object contains exactly one representation:

```json
{"note":"C4"}
```

or:

```json
{"hz":440.0}
```

Note names use scientific pitch notation with optional `#` or `b`. Frequencies must be finite and positive. Renderers may internally map both forms onto a continuous semitone axis; the source representation remains part of the score.

A `pitch_curve` is an ordered array of `{at, pitch}` points. `at` is strictly increasing within `0..1`, where 0 is event onset and 1 is event end. The event's starting `pitch` is the curve origin. This allows glissandi, howls, sirens, bends, and other continuous gestures without decomposing them into fake discrete notes.

## 6. Pitch color semantics

The ESN-1 reference renderer uses a 12-step absolute pitch-class palette. Color belongs to the pitch class, not the sound source. Therefore a cat meowing C4 and a piano playing C4 receive the same pitch-class cue while retaining distinct glyph/source identity.

Relative scale-degree coloration remains intentionally outside ESN-1. It is now specified by `esn-visual/1`, where tonic and scale intervals are renderer context rather than score semantics. This keeps transposable color meaning out of the canonical event format.

## 7. Visual redundancy and accessibility

A compliant renderer must not make hue the only way to recover pitch. The reference renderer redundantly exposes pitch through vertical location, textual note/frequency labeling, and accessible SVG descriptions. Source glyph identity is accompanied by source/gesture text.

Platform emoji art is presentation, not semantic authority. Beadtrain 3 adds `esn-visual/1` with portable in-house SVG source glyphs that can be truly tinted without vendor artwork. Renderers may still use system emoji as fallback as long as underlying source identity remains unchanged.

## 8. Canonicalization

Canonical ESN-1 JSON is UTF-8, object-key sorted, compact JSON with Unicode preserved and one trailing LF. Canonicalization does not reorder the `events` array because event ordering may be meaningful to authoring tools even when onsets are equal.

The registry is external to the score. A renderer or player must validate the score against the selected registry before using source-specific semantics.

## 9. Beadtrain 1 boundary

Beadtrain 1 proves:

1. semantic source + gesture identity;
2. pitched and explicitly unpitched events in one score;
3. note and Hz pitch representation;
4. continuous pitch trajectories;
5. redundant pitch visualization;
6. deterministic validation, canonicalization, and SVG rendering.

Later binding trains now provide executable playback (`esn-playback/1`), browser notation editing, portable custom tintable glyphs, and relative scale-degree coloration (`esn-visual/1`) without changing ESN-1. MIDI/MusicXML interchange, tempo maps, polyphonic source instances, richer articulation registries, sample-pack distribution, and collaboration remain future work.
