# Beadtrain 6: Score Grammar and Composition Model

## Product intent

ESN becomes a notation-first composer for complete audible works, not a flat event timeline and not a DAW with emoji decoration.

The canonical model is:

`Score -> Tracks -> Sections -> Musical Objects -> Realizations`

Semantic meaning remains authoritative. Visual glyphs and audible realizations remain replaceable layers.

A user should be able to compose music, Foley, animals, weather, ambience, and other sound sources entirely inside ESN, then preview/render/export without requiring a DAW to finish the composition.

Mario Paint remains the usability floor: placing a cat, piano, or lightning sound must stay immediate and playful. NoteWorthy-style score structure supplies the compositional depth.

## Core laws

- One primary semantic instrument/source per track section.
- Parallel simultaneous sources use parallel tracks.
- A track can be split into sections; a split creates only a boundary and never rewrites existing content automatically.
- Each new section is explicitly assigned its source/instrument.
- Sections can be polyphonic.
- Pitch is first-class notation, including pitch changes by vertical movement.
- Chords are first-class objects that can be exploded into independent notes.
- The score's semantic identity is independent from both glyph appearance and sound realization.

## Musical context and defaults

Factory defaults are:

- tempo: 96 BPM;
- time signature: 4/4;
- tuning reference: A4 = 432 Hz;
- key/scale: user-settable, with C major as the initial factory key/scale.

Tempo, time signature, key/scale, and tuning defaults are user-settable. Defaults seed new musical material; they are not global laws that silently bind every track.

Each track owns a musical-context map through time. Context changes can alter tempo, meter, key/scale, or tuning for that track without changing unrelated tracks.

A section inherits the active track context at its start unless it explicitly overrides a value. Moving a section boundary does not mutate musical objects or context values.

Tracks may intentionally share the same context values, but independent polymeter/polyrhythm remains legal. A sustained or environmental section may be musically unpitched while still occupying score time.

Absolute clock time is derived from the musical context for playback, rendering, cue sheets, and interchange. Musical placement remains the native authoring model.

## Tracks and sections

A track is a persistent compositional lane through score time. It is not permanently tied to one instrument.

A section is a contiguous track range with exactly one primary semantic source/instrument. Example: `Piano | Cat | Violin` on one track.

Splitting creates an unassigned section boundary first; the user then chooses the new section's source. No source change is inferred merely from the split operation.

## Musical objects

A section contains musical objects rather than only flat events.

Supported object classes for this train:

- note: one pitched or intentionally unpitched event;
- chord: root, quality, inversion/voicing, duration, dynamics, articulation, and optional arpeggiation;
- sustained semantic event: long-form sound such as rain or wind that follows section timing;
- gesture event: source-specific action such as cat/meow or door/slam.

Chord creation is assisted by selectable harmonic vocabularies including major, minor, pentatonic, diminished, augmented, suspended, seventh-family, inversions, and voicings. Scale-aware entry may snap pitches to the active section key/scale.

A chord remains one editable object until the user explicitly explodes it. Explosion materializes its component notes at the same score position and preserves audible intent.

Polyphony is legal for every section. A piano can play chords; a cat can meow a chord. Realization capability affects playback quality, not whether the notation is legal.

## Semantic, visual, and audio realization

The semantic ID remains canonical, for example `animal:cat` plus gesture `meow`.

Visual precedence is:

`project-local glyph -> globally installed glyph -> built-in/reference glyph`

Audio precedence is:

`project-local realization -> globally installed sound pack -> built-in/reference realization`

A lightning semantic source cannot silently resolve to an unrelated engine-start identity. Realizations may stylize or transform a source, but must remain semantically compatible with the source/gesture they claim to implement.

## ESN/2 schema direction

`esn/2` is the canonical score grammar for this train. It replaces the flat top-level `events` array with explicit tracks and sections while preserving the semantic event vocabulary and binding layers from ESN/1.

Every track has a stable ID, name, musical-context map, and ordered sections. Every section has a stable ID, start/end score position, one source identity, optional context overrides, and ordered objects.

Score positions are represented musically, not as floating-point seconds. Rendering derives absolute time from each track's context map.

Existing ESN/1 files remain loadable through a deterministic migration path. Migration places the legacy event set into a valid ESN/2 score without changing source, gesture, onset, duration, pitch, dynamics, articulation, or pitch curves.

Saving an ESN/2 score emits ESN/2. Legacy ESN/1 export may remain available only when the score can be represented without loss; otherwise the product must report the loss instead of flattening silently.

## Editor behavior

The current browser editor evolves rather than being replaced. The visible score gains tracks, section boundaries, per-track musical context, vertical pitch placement, chord entry, and chord explosion.

Basic entry stays immediate: choose a source, place an object, drag horizontally in score time, drag vertically in pitch, and preview.

Advanced controls appear in the existing inspector/context surfaces rather than requiring a separate professional mode. The same object can be manipulated simply or deeply.

Cat-heavy qualification is intentional: the reference composition should visibly prove pitched cat notes, a cat chord, a second simultaneous source on another track, a section split, and a non-default musical context.

## Error handling

Validation rejects overlapping/invalid section ranges, duplicate IDs, objects outside their section, impossible meter values, nonpositive tempo, invalid tuning references, malformed chord definitions, and incompatible semantic source/gesture pairs.

No editor operation may silently rewrite objects merely because a section boundary, default, source assignment, or musical context changed. Operations that would create an invalid score are blocked or normalized explicitly with a visible explanation.

## Data flow

1. Load ESN/2 directly or migrate ESN/1 into ESN/2 in memory.
2. Validate score, track context maps, sections, and musical objects.
3. Resolve semantic source/gesture identity through the existing registry.
4. Resolve visual and audio realization through the existing binding layers.
5. Convert musical positions into absolute playback/render times per track context.
6. Render/preview/export while preserving semantic objects and reporting any interchange loss.

## Qualification

Train 6 is qualified only when the complete composition model works together through the real product.

Required executable coverage includes:

- ESN/2 schema/model validation and deterministic canonicalization;
- deterministic ESN/1 -> ESN/2 migration;
- independent track meter/tempo/key/tuning contexts;
- factory 96 BPM, 4/4, A4=432 behavior and user-settable defaults;
- track splitting with explicit source assignment and no silent object mutation;
- polyphonic notes and chord objects;
- chord explode preserving component pitches/timing;
- browser drag X for musical time and Y for pitch;
- real browser creation/edit/play/save/open of a multi-track cat composition;
- existing sound-pack, visual, MIDI/cue, and deterministic audio contracts either preserved or explicitly version-adapted;
- regression coverage for all previously repaired click/drag and overlapping-MIDI lifetime defects.

The product screenshot set must come from the real browser product, not a mockup, and must visibly include cats.

## Scope boundary

Portable single-file project containers, project-local embedded glyph/audio assets, and global installation of Emojineer glyph packages remain a following ecosystem train. Train 6 establishes the score grammar those packages will attach to; it does not fake that packaging work inside the composition model.
