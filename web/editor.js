"use strict";

const PX_PER_BEAT = 100;
const SEMITONE_PX = 12;
const TOP_MIDI = 84;
const PITCH_TOP = 38;
const UNPITCHED_TOP = 510;

const state = {
  score: null,
  registryDoc: null,
  playbackDoc: null,
  visualDoc: null,
  colorMode: "pitch_class",
  sources: new Map(),
  profiles: new Map(),
  selectedId: null,
  audio: null,
};

const $ = (id) => document.getElementById(id);
const {noteToMidi, midiToNote} = EsnDomain;
const {colorCueForMidi, glyphSvg} = EsnVisualDomain;

async function loadBundled() {
  const [score, registryDoc, playbackDoc, visualDoc] = await Promise.all([
    fetch("../examples/first-score.esn.json").then(r => r.json()),
    fetch("../registries/core.json").then(r => r.json()),
    fetch("../playback/core.json").then(r => r.json()),
    fetch("../visual/core.json").then(r => r.json()),
  ]);
  state.score = structuredClone(score);
  state.registryDoc = registryDoc;
  state.playbackDoc = playbackDoc;
  state.visualDoc = visualDoc;
  state.colorMode = visualDoc.default_mode;
  state.sources = new Map(registryDoc.sources.map(source => [source.id, source]));
  state.profiles = new Map(playbackDoc.profiles.map(profile => [`${profile.source}/${profile.gesture}`, profile]));
  state.selectedId = null;
  renderAll();
  status(`Loaded ${score.events.length} events at ${score.tempo_bpm} BPM with ${visualDoc.name}.`);
}

function sourceFor(event) {
  return state.sources.get(event.source);
}

function profileFor(event) {
  return state.profiles.get(`${event.source}/${event.gesture}`)
      || state.profiles.get(`${event.source}/*`);
}

function pitchMidi(event) {
  if (!event.pitch) return null;
  if (typeof event.pitch.note === "string") return noteToMidi(event.pitch.note);
  if (typeof event.pitch.hz === "number") return 69 + 12 * Math.log2(event.pitch.hz / 440);
  return null;
}

function eventColor(event) {
  const midi = pitchMidi(event);
  if (midi === null) return state.visualDoc.palettes.unpitched;
  return colorCueForMidi(state.visualDoc, midi, state.colorMode).color;
}

function sourceGlyph(sourceId, color, size = 22) {
  return glyphSvg(state.visualDoc, sourceId, color, size);
}

function maxEnd() {
  return Math.max(4, ...state.score.events.map(e => Number(e.onset) + Number(e.duration)));
}

function eventTop(event) {
  const midi = pitchMidi(event);
  if (midi !== null) return PITCH_TOP + (TOP_MIDI - midi) * SEMITONE_PX;
  const unpitched = [...new Set(state.score.events.filter(e => !e.pitch).map(e => e.source))].sort();
  return UNPITCHED_TOP + unpitched.indexOf(event.source) * 46;
}

function renderAll() {
  renderVisualMode();
  renderPalette();
  renderRuler();
  renderTimeline();
  renderInspector();
}

function renderVisualMode() {
  $("color-mode").value = state.colorMode;
  const mode = state.colorMode === "pitch_class"
    ? "absolute pitch class"
    : `relative scale degree · tonic ${state.visualDoc.scale.tonic}`;
  $("color-legend").textContent = `color: ${mode}`;
}

function renderPalette() {
  const root = $("palette");
  root.replaceChildren();
  for (const source of state.registryDoc.sources) {
    const group = document.createElement("div");
    group.className = "source-group";
    group.innerHTML = `<div class="source-name">${sourceGlyph(source.id, state.visualDoc.palettes.unpitched, 22)}<span>${source.id}</span></div>`;
    const gestures = document.createElement("div");
    gestures.className = "gesture-list";
    for (const gesture of source.gestures) {
      const button = document.createElement("button");
      button.className = "gesture-button";
      button.textContent = gesture;
      button.addEventListener("click", () => addEvent(source, gesture));
      gestures.append(button);
    }
    group.append(gestures);
    root.append(group);
  }
}

function renderRuler() {
  const ruler = $("ruler");
  ruler.replaceChildren();
  for (let beat = 0; beat <= Math.ceil(maxEnd()) + 1; beat++) {
    const mark = document.createElement("div");
    mark.className = "ruler-mark";
    mark.style.left = `${beat * PX_PER_BEAT}px`;
    mark.textContent = beat;
    ruler.append(mark);
  }
}

function renderTimeline() {
  const root = $("timeline");
  root.replaceChildren();
  root.style.width = `${Math.max(1000, (maxEnd() + 2) * PX_PER_BEAT)}px`;

  for (let midi = 84; midi >= 48; midi -= 12) {
    const label = document.createElement("span");
    label.className = "pitch-label";
    label.style.top = `${PITCH_TOP + (TOP_MIDI - midi) * SEMITONE_PX}px`;
    label.textContent = midiToNote(midi);
    root.append(label);
  }

  const divider = document.createElement("div");
  divider.className = "unpitched-divider";
  divider.style.top = `${UNPITCHED_TOP - 12}px`;
  root.append(divider);

  const lanes = [...new Set(state.score.events.filter(e => !e.pitch).map(e => e.source))].sort();
  lanes.forEach((source, index) => {
    const label = document.createElement("span");
    label.className = "lane-label";
    label.style.top = `${UNPITCHED_TOP + index * 46 + 8}px`;
    label.textContent = source;
    root.append(label);
  });

  for (const event of state.score.events) {
    const source = sourceFor(event);
    const chip = document.createElement("div");
    chip.className = `event${event.id === state.selectedId ? " selected" : ""}`;
    chip.dataset.id = event.id;
    chip.style.left = `${Number(event.onset) * PX_PER_BEAT}px`;
    chip.style.top = `${eventTop(event)}px`;
    chip.style.width = `${Math.max(38, Number(event.duration) * PX_PER_BEAT)}px`;
    const midi = pitchMidi(event);
    const color = eventColor(event);
    const cue = midi === null ? "unpitched" : colorCueForMidi(state.visualDoc, midi, state.colorMode).label;
    chip.style.color = color;
    chip.innerHTML = `<span class="glyph">${sourceGlyph(event.source, color, 22)}</span><span class="meta">${event.gesture}${event.pitch?.note ? ` · ${event.pitch.note}` : ""} · ${cue}</span>`;
    chip.addEventListener("click", e => {
      e.stopPropagation();
      state.selectedId = event.id;
      renderAll();
    });
    installDrag(chip, event);
    root.append(chip);
  }

  root.addEventListener("click", () => {
    state.selectedId = null;
    renderAll();
  }, {once: true});
}

function installDrag(element, event) {
  element.addEventListener("pointerdown", down => {
    down.stopPropagation();
    element.setPointerCapture(down.pointerId);
    const startX = down.clientX;
    const startY = down.clientY;
    const originalOnset = Number(event.onset);
    const originalMidi = pitchMidi(event);

    const move = current => {
      const beats = Math.round(((current.clientX - startX) / PX_PER_BEAT) * 4) / 4;
      event.onset = Math.max(0, originalOnset + beats);
      if (originalMidi !== null) {
        const semitones = Math.round((startY - current.clientY) / SEMITONE_PX);
        event.pitch = {note: midiToNote(originalMidi + semitones)};
        delete event.pitch_curve;
      }
      element.style.left = `${event.onset * PX_PER_BEAT}px`;
      element.style.top = `${eventTop(event)}px`;
    };
    const up = () => {
      element.removeEventListener("pointermove", move);
      renderAll();
    };
    element.addEventListener("pointermove", move);
    element.addEventListener("pointerup", up, {once: true});
  });
}

function addEvent(source, gesture) {
  const idBase = `${source.id.replace(/[^a-z0-9]+/gi, "-")}-${gesture}`;
  let counter = 1;
  while (state.score.events.some(e => e.id === `${idBase}-${counter}`)) counter++;
  const event = {
    id: `${idBase}-${counter}`,
    source: source.id,
    gesture,
    onset: Math.ceil(maxEnd()),
    duration: 1,
    dynamics: 0.75,
  };
  if (source.pitch_policy === "required") event.pitch = {note: "C4"};
  state.score.events.push(event);
  state.selectedId = event.id;
  renderAll();
  status(`Added ${source.id} ${gesture}.`);
}

function selectedEvent() {
  return state.score.events.find(event => event.id === state.selectedId) || null;
}

function renderInspector() {
  const event = selectedEvent();
  $("empty-inspector").hidden = Boolean(event);
  $("inspector").hidden = !event;
  if (!event) return;
  const source = sourceFor(event);
  $("event-id").value = event.id;
  $("event-source").value = event.source;
  $("event-onset").value = event.onset;
  $("event-duration").value = event.duration;
  $("event-dynamics").value = event.dynamics ?? 0.75;
  $("pitch-row").hidden = source.pitch_policy === "forbidden";
  $("event-pitch").value = event.pitch?.note || "";
  const gestureSelect = $("event-gesture");
  gestureSelect.replaceChildren(...source.gestures.map(gesture => new Option(gesture, gesture)));
  gestureSelect.value = event.gesture;
}

function commitInspector() {
  const event = selectedEvent();
  if (!event) return;
  const source = sourceFor(event);
  event.gesture = $("event-gesture").value;
  event.onset = Math.max(0, Number($("event-onset").value) || 0);
  event.duration = Math.max(0.01, Number($("event-duration").value) || 0.01);
  event.dynamics = Math.max(0, Math.min(1, Number($("event-dynamics").value)));
  if (source.pitch_policy !== "forbidden") {
    const note = $("event-pitch").value.trim();
    if (note) {
      if (noteToMidi(note) === null) return status(`Invalid pitch: ${note}`);
      event.pitch = {note};
    } else if (source.pitch_policy === "required") {
      event.pitch = {note: "C4"};
    } else {
      delete event.pitch;
    }
    delete event.pitch_curve;
  }
  renderAll();
}

function audioContext() {
  if (!state.audio) state.audio = new (window.AudioContext || window.webkitAudioContext)();
  return state.audio;
}

function midiHz(midi) {
  return 440 * 2 ** ((midi - 69) / 12);
}

function previewEvent(event, when = null, durationOverride = null) {
  const ctx = audioContext();
  const profile = profileFor(event);
  if (!profile) return status(`No playback profile for ${event.source}/${event.gesture}`);
  const start = when ?? ctx.currentTime + 0.02;
  const beatSeconds = 60 / Number(state.score.tempo_bpm || 120);
  const duration = durationOverride ?? Number(event.duration) * beatSeconds;
  const gainNode = ctx.createGain();
  gainNode.gain.setValueAtTime(0, start);
  gainNode.gain.linearRampToValueAtTime((profile.gain ?? 0.7) * (event.dynamics ?? 0.75), start + Math.min(profile.attack ?? .01, duration / 2));
  gainNode.gain.setValueAtTime((profile.gain ?? 0.7) * (event.dynamics ?? 0.75), start + duration);
  gainNode.gain.linearRampToValueAtTime(0, start + duration + (profile.release ?? .05));
  gainNode.connect(ctx.destination);

  if (profile.mode === "oscillator") {
    const osc = ctx.createOscillator();
    osc.type = ["sine","square","sawtooth","triangle"].includes(profile.wave) ? profile.wave : (profile.wave === "saw" ? "sawtooth" : "sine");
    const midi = pitchMidi(event);
    osc.frequency.setValueAtTime(midi === null ? (profile.base_hz ?? 440) : midiHz(midi), start);
    for (const point of event.pitch_curve || []) {
      const pointMidi = point.pitch.note ? noteToMidi(point.pitch.note) : 69 + 12 * Math.log2(point.pitch.hz / 440);
      osc.frequency.linearRampToValueAtTime(midiHz(pointMidi), start + point.at * duration);
    }
    osc.connect(gainNode);
    osc.start(start);
    osc.stop(start + duration + (profile.release ?? .05));
    return;
  }

  const frames = Math.max(1, Math.floor(ctx.sampleRate * (profile.mode === "impulse" ? Math.min(0.18, duration) : duration)));
  const buffer = ctx.createBuffer(1, frames, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < frames; i++) {
    const noise = Math.random() * 2 - 1;
    data[i] = profile.mode === "impulse" ? noise * Math.exp(-18 * i / ctx.sampleRate) : noise;
  }
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(gainNode);
  source.start(start);
}

function playScore() {
  const ctx = audioContext();
  const beatSeconds = 60 / Number(state.score.tempo_bpm || 120);
  const base = ctx.currentTime + 0.05;
  for (const event of state.score.events) previewEvent(event, base + Number(event.onset) * beatSeconds);
  status(`Playing ${state.score.events.length} events.`);
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  }
  return value;
}

function exportScore() {
  const text = JSON.stringify(canonical(state.score), null, 2) + "\n";
  const blob = new Blob([text], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "edited-score.esn.json";
  a.click();
  URL.revokeObjectURL(url);
  status("Exported canonical-key-order ESN JSON.");
}

function status(message) {
  $("status").textContent = message;
}

for (const id of ["event-gesture","event-onset","event-duration","event-pitch","event-dynamics"]) {
  $(id).addEventListener("change", commitInspector);
}
$("color-mode").addEventListener("change", event => {
  state.colorMode = event.target.value;
  renderAll();
  status(`Visual color mode: ${state.colorMode}.`);
});
$("reload").addEventListener("click", loadBundled);
$("play-score").addEventListener("click", playScore);
$("export").addEventListener("click", exportScore);
$("play-event").addEventListener("click", () => {
  const event = selectedEvent();
  if (event) previewEvent(event);
});
$("delete-event").addEventListener("click", () => {
  const event = selectedEvent();
  if (!event) return;
  state.score.events = state.score.events.filter(candidate => candidate.id !== event.id);
  state.selectedId = null;
  renderAll();
  status(`Deleted ${event.id}.`);
});

loadBundled().catch(error => status(`Load failed: ${error.message}. Serve the repository root over HTTP.`));
