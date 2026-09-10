"use strict";

(function exposeVisualDomain(root) {
  const OFFSETS = {C:0,D:2,E:4,F:5,G:7,A:9,B:11};
  const PC_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];

  function tonicPitchClass(tonic) {
    const match = /^([A-Ga-g])([#b]?)$/.exec(tonic || "");
    if (!match) return null;
    let pitch = OFFSETS[match[1].toUpperCase()];
    if (match[2] === "#") pitch += 1;
    if (match[2] === "b") pitch -= 1;
    return ((pitch % 12) + 12) % 12;
  }

  function colorCueForMidi(profile, midi, mode = null) {
    const selected = mode || profile.default_mode;
    const pitchClass = ((Math.floor(midi + 0.5) % 12) + 12) % 12;
    if (selected === "pitch_class") {
      return {color: profile.palettes.pitch_class[pitchClass], label: `pitch class ${PC_NAMES[pitchClass]}`};
    }
    if (selected !== "scale_degree") throw new Error(`unknown visual color mode: ${selected}`);
    const tonic = tonicPitchClass(profile.scale.tonic);
    if (tonic === null) throw new Error(`invalid visual tonic: ${profile.scale.tonic}`);
    const relative = (pitchClass - tonic + 12) % 12;
    const degree = profile.scale.intervals.indexOf(relative);
    if (degree < 0) return {color: profile.palettes.chromatic, label: "chromatic outside configured scale"};
    return {color: profile.palettes.scale_degree[degree], label: `scale degree ${degree + 1}`};
  }

  function glyphForSource(profile, sourceId) {
    return profile.glyphs.find(glyph => glyph.source === sourceId) || null;
  }

  function escapeAttr(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll('"', "&quot;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function glyphSvg(profile, sourceId, color, size = 24) {
    const glyph = glyphForSource(profile, sourceId);
    if (!glyph) throw new Error(`visual glyph not found for source: ${sourceId}`);
    const detail = glyph.details
      ? `<path d="${escapeAttr(glyph.details)}" fill="none" stroke="${escapeAttr(profile.style.detail)}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>`
      : "";
    return `<svg class="canonical-glyph" viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true" focusable="false">`
      + `<path d="${escapeAttr(glyph.path)}" fill="${escapeAttr(color)}" stroke="${escapeAttr(profile.style.stroke)}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>`
      + detail + `</svg>`;
  }

  const api = {tonicPitchClass, colorCueForMidi, glyphForSource, glyphSvg};
  root.EsnVisualDomain = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
