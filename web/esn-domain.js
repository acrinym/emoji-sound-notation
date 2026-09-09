"use strict";

(function exposeEsnDomain(root) {
  function noteToMidi(note) {
    const match = /^([A-Ga-g])([#b]?)(-?\d+)$/.exec(note || "");
    if (!match) return null;
    const offsets = {C:0,D:2,E:4,F:5,G:7,A:9,B:11};
    let pitch = offsets[match[1].toUpperCase()];
    if (match[2] === "#") pitch += 1;
    if (match[2] === "b") pitch -= 1;
    const midi = (Number(match[3]) + 1) * 12 + pitch;
    return Number.isInteger(midi) && midi >= 0 && midi <= 127 ? midi : null;
  }

  function midiToNote(midi) {
    const names = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
    const rounded = Math.max(0, Math.min(127, Math.round(midi)));
    return `${names[rounded % 12]}${Math.floor(rounded / 12) - 1}`;
  }

  const api = {noteToMidi, midiToNote};
  root.EsnDomain = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
