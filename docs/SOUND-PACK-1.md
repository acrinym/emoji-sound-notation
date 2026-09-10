# ESN Sound Pack 1

`esn-sound-pack/1` is the realization layer for Emoji Sound Notation.

Its job is deliberately narrow:

> Change how an ESN event is heard without changing what the event means.

A semantic event such as `animal:cat` + `meow` remains the same ESN event whether it is heard through the built-in reference synth, a recorded cat sample, a stylized game-SFX pack, or a user-selected WAV.

## Separation of concerns

- `esn/1` owns semantic event identity, timing, pitch, dynamics, and articulation.
- `esn-playback/1` owns deterministic reference-synth behavior.
- `esn-sound-pack/1` optionally binds semantic source/action pairs to WAV realizations.
- `esn-visual/1` owns glyph/color representation.
- `esn-interchange/1` owns MIDI/cue-sheet handoff.

Sound-pack choice is therefore not serialized into the ESN score. A saved project can be opened under another pack without rewriting its semantics.

## Manifest

A pack is a folder containing one `esn-sound-pack/1` JSON manifest and zero or more WAV assets.

```json
{
  "format": "esn-sound-pack/1",
  "id": "example.realistic-animals",
  "name": "Example Realistic Animals",
  "version": "1.0.0",
  "license": {"name": "CC0-1.0", "spdx": "CC0-1.0"},
  "provenance": {"creator": "Example Creator", "source": "Original field recordings"},
  "fallback": "reference_synth",
  "bindings": [
    {
      "source": "animal:cat",
      "gesture": "meow",
      "asset": "samples/cat-meow.wav",
      "gain": 0.9,
      "root_note": "A4",
      "credit": "Example Creator"
    }
  ]
}
```

## Binding resolution

Resolution is deterministic:

1. exact `source` + `gesture` binding;
2. `source` + `*` wildcard binding;
3. reference synth fallback.

A local browser WAV override takes priority over a loaded pack for the matching source/action during that browser session.

## Asset contract

Assets must be relative `.wav` paths inside the pack folder. Absolute paths and `..` traversal are rejected.

The Python conformance renderer accepts uncompressed PCM WAV:

- mono or stereo;
- 8-bit or 16-bit PCM;
- arbitrary source sample rate, resampled deterministically to the active playback rate.

Stereo is mixed to mono for the deterministic reference render.

Optional binding controls:

- `gain`: linear multiplier from 0 through 4;
- `loop`: repeat the sample to fill the event duration;
- `root_note`: pitch represented by the original WAV, allowing pitched ESN events and pitch curves to alter playback rate;
- `credit`: binding-specific attribution text.

## Fallback behavior

`fallback` is required and currently must be `reference_synth`.

A missing, unreadable, unsupported, or empty sample asset does not change or delete the semantic ESN event. Rendering falls back to its `esn-playback/1` profile.

This is intentional: a realization failure must not become semantic data loss.

## Browser workflow

The local editor supports:

- loading a sound-pack folder;
- seeing pack creator/license/provenance metadata;
- seeing missing-sample accounting;
- selecting a sound and seeing which realization is active;
- attaching a local WAV override to a source/action;
- optionally assigning its root pitch and loop behavior;
- clearing the local override;
- returning to the Reference Synth pack.

Pack and local-sample choices remain local runtime state. `Save project` writes the ESN score only.

## CLI

```powershell
esn sound-pack-validate --sound-pack soundpacks/reference.json --registry registries/core.json
esn audio examples/first-score.esn.json --registry registries/core.json --playback playback/core.json --sound-pack path/to/pack.json -o score.wav
```

The bundled `soundpacks/reference.json` intentionally contains zero sample bindings. It names the reference-synth realization explicitly and provides the same sound-pack selection surface without bundling third-party recordings.

## Determinism

The Python renderer is the conformance surface for offline WAV output. Given the same score, playback profile, pack manifest, and WAV bytes, it emits the same PCM WAV bytes.

Browser Web Audio is the interactive preview surface. It follows the same realization priority and pitch-root model, but browser audio output itself is not used as the byte-deterministic conformance artifact.
