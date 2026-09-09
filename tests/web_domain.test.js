"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {noteToMidi, midiToNote} = require("../web/esn-domain.js");

test("browser note parsing matches the ESN MIDI range", () => {
  assert.equal(noteToMidi("C4"), 60);
  assert.equal(noteToMidi("G9"), 127);
  assert.equal(noteToMidi("C-1"), 0);
  assert.equal(noteToMidi("C100"), null);
  assert.equal(noteToMidi("Cb-1"), null);
  assert.equal(noteToMidi("not-a-note"), null);
});

test("dragged pitches remain inside the ESN MIDI range", () => {
  assert.equal(midiToNote(-12), "C-1");
  assert.equal(midiToNote(140), "G9");
});

const {colorCueForMidi, glyphSvg, tonicPitchClass} = require("../web/visual-domain.js");
const visual = require("../visual/core.json");

test("browser visual colors support pitch class and transposable scale degree", () => {
  assert.equal(tonicPitchClass("C"), 0);
  assert.equal(tonicPitchClass("Bb"), 10);
  assert.equal(colorCueForMidi(visual, 60, "pitch_class").label, "pitch class C");
  assert.equal(colorCueForMidi(visual, 60, "scale_degree").label, "scale degree 1");
  const shifted = structuredClone(visual);
  shifted.scale.tonic = "D";
  assert.equal(
    colorCueForMidi(visual, 60, "scale_degree").color,
    colorCueForMidi(shifted, 62, "scale_degree").color,
  );
  assert.equal(colorCueForMidi(visual, 61, "scale_degree").color, visual.palettes.chromatic);
});

test("browser canonical glyphs are tintable SVG geometry", () => {
  const red = glyphSvg(visual, "animal:cat", "#ff0000", 22);
  const blue = glyphSvg(visual, "animal:cat", "#0000ff", 22);
  assert.match(red, /<svg class="canonical-glyph"/);
  assert.match(red, /#ff0000/);
  assert.match(blue, /#0000ff/);
  assert.notEqual(red, blue);
  assert.doesNotMatch(red, /🐈/);
});

test("visual half-semitone rounding matches the Python contract", () => {
  const cue = colorCueForMidi(visual, 60.5, "pitch_class");
  assert.equal(cue.label, "pitch class C#");
  assert.equal(cue.color, visual.palettes.pitch_class[1]);
});

const {classification, cueRows, cueCsv} = require("../web/interchange-domain.js");
const interchange = require("../interchange/core.json");
const score = require("../examples/first-score.esn.json");

test("browser cue classification preserves mapped and cue-only semantics", () => {
  const piano = score.events.find(event => event.id === "piano-c4");
  const rain = score.events.find(event => event.id === "rain-bed");
  const drum = score.events.find(event => event.id === "drum-hit");
  assert.deepEqual(classification(piano, interchange, noteToMidi), {status:"midi_note", channel:1, note:60});
  assert.deepEqual(classification(rain, interchange, noteToMidi), {status:"cue_only", channel:"", note:""});
  assert.deepEqual(classification(drum, interchange, noteToMidi), {status:"midi_note", channel:10, note:36});
});

test("browser cue CSV contains every semantic event with real-time timing", () => {
  const rows = cueRows(score, interchange, noteToMidi);
  assert.equal(rows.length, score.events.length);
  assert.equal(rows.find(row => row.id === "door-slam").start_seconds, "2.343750");
  const csv = cueCsv(score, interchange, noteToMidi);
  assert.equal(csv.trimEnd().split("\n").length, score.events.length + 1);
  assert.match(csv, /rain-bed,nature:rain,fall/);
});

const {createHash} = require("node:crypto");
const {midiBytes} = require("../web/interchange-domain.js");

test("browser MIDI exporter stays byte-identical to the conformance artifact", () => {
  const {bytes, report} = midiBytes(score, interchange, noteToMidi);
  const hash = createHash("sha256").update(Buffer.from(bytes)).digest("hex").toUpperCase();
  assert.equal(report.events_total, 6);
  assert.equal(report.midi_notes, 3);
  assert.equal(report.cue_only, 3);
  assert.equal(hash, "356D77D2EAE8DEDE53CCD18AAC8FBF337975665019CBB9E828F2347EC9BFCC14");
});
