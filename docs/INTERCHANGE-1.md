# ESN Interchange Binding 1

Status: Beadtrain 4
Format identifier: `esn-interchange/1`

## Purpose

ESN can describe sounds that ordinary MIDI cannot: rain, doors, animal vocalizations, Foley, and other explicitly unpitched or source-specific events. Interchange therefore MUST be loss-aware rather than silently dropping those events or inventing musical notes for them.

The core bridge produces two complementary outputs:

1. Standard MIDI File Type 1 for material that has an intentional MIDI mapping;
2. a deterministic production cue sheet containing every ESN event.

Every MIDI export also carries a timed ESN semantic cue for every source event, including events that also become MIDI notes.

## Mapping profile

`interchange/core.json` defines MIDI mappings separately from ESN semantics. A mapping selects a source, mode, channel, and optionally program or fixed note.

- `pitched`: the ESN event must have pitch; its rounded MIDI pitch becomes the MIDI note.
- `fixed`: every event for that source uses the configured MIDI note, useful for percussion.
- an unmapped source remains cue-only and is never silently discarded.

Changing this profile changes only interchange behavior, never ESN source or gesture identity.

## Standard MIDI File contract

The reference exporter writes SMF Type 1 with a fixed ticks-per-quarter resolution from the profile.

- Track 0 is the conductor track and carries sequence name and tempo.
- Each mapped semantic source receives a deterministic MIDI track.
- Pitched mappings use ESN pitch, onset, duration, and dynamics-derived velocity.
- Fixed mappings use the configured note while preserving timing and dynamics.
- Program changes are emitted only when the mapping declares a program.
- MIDI events are deterministically ordered at equal ticks so note-off precedes note-on.

A final `ESN Semantic Cues` track contains standard Cue Point meta events. Cue text begins with the configured ASCII prefix and contains compact ASCII-safe JSON describing the complete ESN event.

This means an event may be both playable MIDI and a semantic cue. Cue-only events still remain visible to software that exposes MIDI cue points or track metadata.

## Loss accounting

The exporter returns a machine-readable report with counts and per-event classifications:

- `midi_note`: a playable note was emitted;
- `cue_only`: no core MIDI mapping applied;
- `pitch_required`: a pitched mapping could not run because the ESN event had no pitch;
- `pitch_curve_flattened`: MIDI playback uses the event's starting pitch while the full curve remains in the semantic cue.

No ESN event is omitted from both MIDI and cue output.

## Production cue sheet

CSV export contains one row per ESN event with stable ordering and these fields:

`id, source, gesture, onset_beats, end_beats, start_seconds, end_seconds, duration_seconds, pitch, dynamics, articulation, midi_status, midi_channel, midi_note`

Seconds are derived from ESN-1's single `tempo_bpm`. This is directly useful as a handoff/annotation surface for sound design, Foley, game audio, field recording, and editorial workflows even when the destination has no MIDI support.

The browser editor can download the same semantic cue-sheet columns from the currently edited score.

## Boundary

SMF export is not a claim that MIDI can encode ESN semantics natively. MIDI notes are a compatibility projection. ESN semantic cues and the cue sheet remain the authoritative loss/accounting surfaces.

MusicXML belongs to a later notation-focused train. It is useful for conventional pitched notation, but should not be forced to become the storage model for rain, doors, animal sounds, and other non-score-first ESN material.
