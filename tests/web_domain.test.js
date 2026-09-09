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
