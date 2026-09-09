# ESN Visual Binding 1

Status: Beadtrain 3
Format identifier: `esn-visual/1`

## Purpose

ESN-1 defines what a sound event means. `esn-visual/1` is a separate renderer binding that defines portable canonical source glyph geometry and redundant pitch coloration. Changing a visual profile never changes source, gesture, timing, pitch, dynamics, or articulation semantics.

The visual layer solves two portability problems:

1. platform emoji artwork cannot be reliably recolored or reproduced identically;
2. pitch color may be useful either as an absolute pitch-class cue or a relative scale-degree cue.

The core profile therefore contains in-house SVG path geometry for each semantic source. The geometry is deliberately simple, tintable, deterministic, and independent of vendor emoji fonts.

## Profile structure

A visual profile contains:

- `default_mode`: `pitch_class` or `scale_degree`;
- `scale.tonic`: pitch class such as `C`, `F#`, or `Bb`;
- `scale.intervals`: ordered semitone offsets from the tonic;
- 12 absolute pitch-class colors;
- one scale-degree color per configured interval;
- explicit chromatic and unpitched colors;
- renderer stroke/detail colors;
- one canonical glyph binding for every semantic source.

## Color semantics

### Pitch-class mode

`round(MIDI) mod 12` selects one of the 12 palette entries. A C from a piano and a C from a cat use the same color while retaining different canonical glyphs and source labels.

### Scale-degree mode

The pitch class is measured relative to `scale.tonic`. If the relative semitone exists in `scale.intervals`, its interval index selects the scale-degree palette entry. If it is outside the configured scale, the explicit `chromatic` color is used.

Changing tonic transposes the color relationship without changing the score. For example, a major-scale degree-1 event receives the same degree color whether the visual context is C major or D major.

## Canonical glyphs

Each glyph binding contains:

- `source`: ESN semantic source id;
- `id`: portable visual identifier;
- `path`: primary SVG path geometry in a 24x24 coordinate space;
- optional `details`: secondary stroke-only geometry.

The primary geometry is filled with the event color. This produces true custom colorways rather than attempting to recolor platform emoji bitmaps. The default registry emoji remains a fallback/source-language hint, not visual authority.

## Accessibility and redundancy

Hue MUST NOT be the only carrier of pitch or source identity. A compliant rendered score preserves pitch position and textual pitch/source/gesture labels or equivalent accessible descriptions. Canonical glyphs are also accompanied by source/gesture text in reference output.

Unpitched events never acquire fake pitch colors. They use the visual profile's explicit `unpitched` color and remain in unpitched/spectral lanes.

## Determinism

Given the same ESN score, semantic registry, visual profile, and requested color mode, the reference renderer and glyph-sheet generator must produce byte-identical SVG text.
