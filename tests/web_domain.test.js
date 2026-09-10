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
const {midiBytes, midiPlan} = require("../web/interchange-domain.js");

test("browser MIDI exporter stays byte-identical to the conformance artifact", () => {
  const {bytes, report} = midiBytes(score, interchange, noteToMidi);
  const hash = createHash("sha256").update(Buffer.from(bytes)).digest("hex").toUpperCase();
  assert.equal(report.events_total, 6);
  assert.equal(report.midi_notes, 3);
  assert.equal(report.cue_only, 3);
  assert.equal(hash, "356D77D2EAE8DEDE53CCD18AAC8FBF337975665019CBB9E828F2347EC9BFCC14");
});

test("browser MIDI isolates overlapping same-note lifetimes", () => {
  const overlap = {
    format: "esn/1", title: "Overlap", tempo_bpm: 120,
    events: [
      {id:"first", source:"instrument:piano", gesture:"strike", onset:0, duration:2, pitch:{note:"C4"}, dynamics:0.7},
      {id:"second", source:"instrument:piano", gesture:"strike", onset:1, duration:2, pitch:{note:"C4"}, dynamics:0.8},
    ],
  };
  const plan = midiPlan(overlap, interchange, noteToMidi);
  assert.equal(plan.get("first").channel, 0);
  assert.equal(plan.get("second").channel, 2);
  assert.ok(plan.get("second").losses.includes("overlap_channel_reassigned"));
  const {bytes, report} = midiBytes(overlap, interchange, noteToMidi);
  const hash = createHash("sha256").update(Buffer.from(bytes)).digest("hex").toUpperCase();
  assert.equal(hash, "2FC7433B4B71D118821C59D30AB1A09664748025EDF291A00F177AFE437EA2A1");
  assert.equal(report.midi_notes, 2);
  const rows = cueRows(overlap, interchange, noteToMidi);
  assert.equal(rows.find(row => row.id === "second").midi_channel, "3");
  assert.match(rows.find(row => row.id === "second").midi_status, /overlap_channel_reassigned/);
});

const SoundPack = require("../web/sound-pack-domain.js");
const registry = require("../registries/core.json");
const referencePack = require("../soundpacks/reference.json");

test("browser sound-pack contract keeps reference playback as an explicit fallback", () => {
  const validated = SoundPack.validatePack(structuredClone(referencePack), registry, noteToMidi);
  assert.equal(validated.format, "esn-sound-pack/1");
  assert.equal(validated.bindings.length, 0);
  assert.equal(validated.fallback, "reference_synth");
});

test("browser sound-pack resolver prefers exact action then source wildcard", () => {
  const pack = structuredClone(referencePack);
  pack.id = "test.pack"; pack.name = "Test Pack";
  pack.bindings = [
    {source:"animal:cat", gesture:"*", asset:"samples/cat.wav"},
    {source:"animal:cat", gesture:"meow", asset:"samples/meow.wav", root_note:"C4", loop:false},
  ];
  SoundPack.validatePack(pack, registry, noteToMidi);
  assert.equal(SoundPack.resolveBinding(pack, {source:"animal:cat", gesture:"meow"}).asset, "samples/meow.wav");
  assert.equal(SoundPack.resolveBinding(pack, {source:"animal:cat", gesture:"purr"}).asset, "samples/cat.wav");
});

test("browser sound-pack validation rejects traversal and unknown semantics", () => {
  const traversal = structuredClone(referencePack);
  traversal.bindings = [{source:"animal:cat", gesture:"meow", asset:"../outside.wav"}];
  assert.throws(() => SoundPack.validatePack(traversal, registry, noteToMidi), /relative \.wav path/);
  const unknown = structuredClone(referencePack);
  unknown.bindings = [{source:"animal:cat", gesture:"teleport", asset:"samples/nope.wav"}];
  assert.throws(() => SoundPack.validatePack(unknown, registry, noteToMidi), /invalid action/);
});


test("sound-pack description does not duplicate identical SPDX text", () => {
  const pack = require("../soundpacks/reference.json");
  const {describePack} = require("../web/sound-pack-domain.js");
  const text = describePack(pack);
  assert.equal((text.match(/MIT/g) || []).length, 1);
});
