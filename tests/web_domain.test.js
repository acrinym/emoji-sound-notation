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


const ScoreDomain = require("../web/score-domain.js");

test("browser ESN2 score domain uses 96 BPM, 4/4 and A4=432 factory defaults", () => {
  assert.deepEqual(ScoreDomain.factoryDefaults(), {
    tempo_bpm: 96,
    time_signature: {numerator: 4, denominator: 4},
    key: {tonic: "C", scale: "major"},
    tuning: {a4_hz: 432},
  });
  assert.equal(ScoreDomain.TICKS_PER_QUARTER, 9600);
});

test("browser ESN2 cat chords expand and explode like the Python score domain", () => {
  const score2 = {
    format:"esn/2", title:"Cat Chord", length_ticks:8*ScoreDomain.TICKS_PER_QUARTER,
    defaults:ScoreDomain.factoryDefaults(),
    tracks:[{id:"cats",name:"Cat Chorus",context:{},sections:[{
      id:"cats-a",start_tick:0,end_tick:8*ScoreDomain.TICKS_PER_QUARTER,source:"animal:cat",context:{},
      objects:[{id:"cat-c",type:"chord",gesture:"meow",tick:ScoreDomain.TICKS_PER_QUARTER,duration_ticks:ScoreDomain.TICKS_PER_QUARTER,root:"C4",quality:"major",inversion:0,dynamics:.8}],
    }]}],
  };
  ScoreDomain.validateScoreV2(score2, registry, noteToMidi);
  assert.deepEqual(ScoreDomain.expandChordPitches(score2.tracks[0].sections[0].objects[0], noteToMidi), ["C4","E4","G4"]);
  const exploded = ScoreDomain.explodeChord(score2, "cat-c", registry, noteToMidi);
  assert.deepEqual(exploded.tracks[0].sections[0].objects.map(obj => obj.pitch.note), ["C4","E4","G4"]);
});

test("browser section split is explicit and never invents a new source", () => {
  const migrated = ScoreDomain.migrateV1ToV2(score, registry, noteToMidi);
  const piano = migrated.tracks.find(track => track.sections[0].source === "instrument:piano");
  const splitAt = 4 * ScoreDomain.TICKS_PER_QUARTER;
  const split = ScoreDomain.splitSection(migrated, piano.id, piano.sections[0].id, splitAt);
  assert.equal(split.tracks.find(track => track.id === piano.id).sections[1].source, null);
  ScoreDomain.validateScoreV2(split, registry, noteToMidi);
});

test("browser repeated split uses unique section ids", () => {
  let migrated = ScoreDomain.migrateV1ToV2(score, registry, noteToMidi);
  const piano = migrated.tracks.find(track => track.sections[0].source === "instrument:piano");
  migrated = ScoreDomain.splitSection(migrated, piano.id, piano.sections[0].id, 4 * ScoreDomain.TICKS_PER_QUARTER);
  migrated = ScoreDomain.splitSection(migrated, piano.id, piano.sections[0].id, 2 * ScoreDomain.TICKS_PER_QUARTER);
  const ids = migrated.tracks.find(track => track.id === piano.id).sections.map(section => section.id);
  assert.deepEqual(ids, [`${piano.sections[0].id}`, `${piano.sections[0].id}-split-2`, `${piano.sections[0].id}-split`]);
  ScoreDomain.validateScoreV2(migrated, registry, noteToMidi);
});

test("browser ESN1 migration preserves semantics and exact real-time placement", () => {
  const migrated = ScoreDomain.migrateV1ToV2(score, registry, noteToMidi);
  ScoreDomain.validateScoreV2(migrated, registry, noteToMidi);
  const rows = ScoreDomain.documentRows(migrated, registry, noteToMidi);
  const byId = new Map(rows.map(row => [row.event.id, row]));
  assert.equal(migrated.defaults.tempo_bpm, 96);
  assert.equal(migrated.defaults.tuning.a4_hz, 432);
  assert.equal(byId.get("door-slam").onset_seconds, 3.75 * .625);
  assert.ok(Math.abs(byId.get("door-slam").duration_seconds - (.22 * .625)) < 1e-12);
});

test("browser track/section context resolves independent tempo and tuning", () => {
  const migrated = ScoreDomain.migrateV1ToV2(score, registry, noteToMidi);
  const cat = migrated.tracks.find(track => track.sections[0].source === "animal:cat");
  cat.context = {tempo_bpm:120, tuning:{a4_hz:444}};
  cat.sections[0].context = {tempo_bpm:60, tuning:{a4_hz:432}};
  const row = ScoreDomain.documentRows(migrated, registry, noteToMidi).find(item => item.event.id === "cat-meow");
  assert.equal(row.tempo_bpm, 60);
  assert.equal(row.a4_hz, 432);
  assert.equal(row.onset_seconds, 1);
});
