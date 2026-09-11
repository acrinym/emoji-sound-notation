# ESN/2 Score Grammar

ESN/2 adds composition structure to Emoji Sound Notation without changing the semantic identity of a sound source and gesture. ESN/1 remains supported, and legacy projects can be migrated deterministically into the ESN/2 score model.

## Factory defaults

A new ESN/2 score starts with:

- tempo: **96 BPM**;
- meter: **4/4**;
- key: **C major**;
- tuning: **A4 = 432 Hz**;
- timing resolution: **9600 ticks per quarter note**.

These are defaults, not global restrictions. Tracks and sections may override musical context independently.

## Score hierarchy

An ESN/2 document has this shape:

`score -> tracks -> sections -> objects`

The score owns the document title, total length, defaults, optional metadata, and one or more tracks. Every ID across tracks, sections, and objects must be unique.

A track has a stable ID, a customer-facing name, optional context overrides, and one or more sections. A track may therefore run at a different tempo, meter, key, scale, or tuning from another track in the same score.

## Sections and source identity

A section occupies an explicit half-open tick range inside a track. Sections on the same track may touch or leave gaps, but they may not overlap.

Each populated section has exactly one semantic source such as `animal:cat`, `instrument:piano`, or `nature:rain`. A newly split section is intentionally created with `source: null` and no objects. The user must explicitly assign a source before placing sound objects into it; the editor never invents a semantic source during a split.

Section splitting is only legal when the split tick is strictly inside the section and does not cut or move an existing object. Repeated splits generate unique section IDs.

Context resolves in this order:

`score defaults -> track context -> section context`

Later layers override only the fields they provide. Supported context fields are tempo, time signature, key/scale, and A4 tuning.

## Sound objects

A section may contain three object types:

- `note`: a pitched source/gesture with a required pitch;
- `event`: a source/gesture that may be unpitched or optionally pitched according to the semantic registry;
- `chord`: a pitched semantic source/gesture expanded from a root and harmonic quality.

Every object has a stable ID, gesture, tick, duration, dynamics, and articulation. Objects must fit completely inside their containing section, and gestures must be valid for the section source.

## Chords and polyphony

Chord objects make polyphony first-class instead of encoding it as unrelated flat events. Supported qualities are:

- major, minor, diminished, augmented;
- sus2, sus4;
- dominant7, major7, minor7;
- major pentatonic and minor pentatonic stacks.

A chord may select an inversion, `close` or `open` voicing, and optional up/down arpeggiation with an integer tick step. Chord expansion must remain inside the valid MIDI note range.

`explode chord` converts the chord object into independent note objects while preserving source, gesture, timing, dynamics, articulation, and the expanded pitches. This is an authoring transformation, not a change in semantic source identity.

## Timing and adapters

ESN/2 stores musical placement in integer ticks. Adapter code flattens score objects only when an existing subsystem needs an event-style stream.

Flattened rows retain:

- track, section, object, and generated voice identity;
- exact tick and duration values;
- real-time onset and duration after track/section tempo resolution;
- effective meter, key/scale, and A4 tuning;
- the semantic source and gesture used by playback, visual, cue, and interchange layers.

This keeps the richer score grammar isolated from renderer-specific contracts while allowing existing playback, SVG, cue-sheet, MIDI, and sound-pack layers to continue operating.

## ESN/1 migration

Migration validates the original ESN/1 document, preserves its title and metadata, and carries its scene tempo into the ESN/2 defaults. Events are grouped by semantic source into separate tracks, with one full-length section per source.

Legacy event IDs, gestures, onset/duration, pitch, pitch curves, dynamics, and articulation are preserved. Musical onset and duration are converted deterministically into ESN/2 ticks.

Migration does not pretend ESN/1 had track-local meter, key, or tuning. The migrated score receives the ESN/2 factory values for those fields while preserving the original ESN/1 tempo.

## Validation boundaries

ESN/2 rejects, among other invalid states:

- unknown fields at score, track, section, or object level;
- duplicate IDs;
- empty tracks or sections;
- overlapping or out-of-range section spans;
- populated sections with no source;
- objects outside their section;
- semantic source/gesture mismatches;
- impossible meter denominators or nonpositive tempo;
- invalid tuning values;
- malformed pitches, pitch curves, chords, inversions, voicings, or arpeggiation.

The machine-readable contract is [`esn-2.schema.json`](esn-2.schema.json). The cat-heavy executable example is [`../examples/cat-counterpoint.esn.json`](../examples/cat-counterpoint.esn.json).

## Browser authoring

The browser composer exposes the same model directly: score defaults, track context, section selection/splitting/source assignment, note/event placement, chord creation and explosion, drag-based placement/transposition, Save/New/Open, preview, cue export, MIDI export, and the existing sound-realization controls.

The saved project is semantic ESN/2. Sound-pack and local-WAV realization state remains separate from the score contract.
