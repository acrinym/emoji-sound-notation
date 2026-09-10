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
  interchangeDoc: null,
  soundPackDoc: null,
  referenceSoundPackDoc: null,
  soundPackManifestPath: "",
  soundPackFiles: new Map(),
  localSamples: new Map(),
  sampleBuffers: new Map(),
  colorMode: "pitch_class",
  sources: new Map(),
  profiles: new Map(),
  selectedId: null,
  audio: null,
  ignoreTimelineClick: false,
};

const $ = (id) => document.getElementById(id);
const {noteToMidi, midiToNote} = EsnDomain;
const {colorCueForMidi, glyphSvg} = EsnVisualDomain;
const {cueCsv, midiBytes} = EsnInterchangeDomain;
const {validatePack, resolveBinding, fileKeyFor, describePack} = EsnSoundPackDomain;

async function loadBundled() {
  const [score, registryDoc, playbackDoc, visualDoc, interchangeDoc, soundPackDoc] = await Promise.all([
    fetch("../examples/first-score.esn.json").then(r => r.json()),
    fetch("../registries/core.json").then(r => r.json()),
    fetch("../playback/core.json").then(r => r.json()),
    fetch("../visual/core.json").then(r => r.json()),
    fetch("../interchange/core.json").then(r => r.json()),
    fetch("../soundpacks/reference.json").then(r => r.json()),
  ]);
  state.registryDoc = registryDoc;
  state.playbackDoc = playbackDoc;
  state.visualDoc = visualDoc;
  state.interchangeDoc = interchangeDoc;
  state.soundPackDoc = validatePack(soundPackDoc, registryDoc, noteToMidi);
  state.referenceSoundPackDoc = structuredClone(state.soundPackDoc);
  state.soundPackManifestPath = "soundpacks/reference.json";
  state.soundPackFiles = new Map();
  state.colorMode = visualDoc.default_mode;
  state.sources = new Map(registryDoc.sources.map(source => [source.id, source]));
  state.profiles = new Map(playbackDoc.profiles.map(profile => [`${profile.source}/${profile.gesture}`, profile]));
  applyScore(score, `Ready: ${score.events.length} sounds at ${score.tempo_bpm} BPM.`);
}

function sourceFor(event) {
  return state.sources.get(event.source);
}

function titleWords(value) {
  return String(value).replace(/[-_]/g, " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function sourceLabel(sourceId) {
  return titleWords(String(sourceId).split(":").at(-1));
}

function actionLabel(gesture) {
  return titleWords(gesture);
}

function realizationKey(event) {
  return `${event.source}/${event.gesture}`;
}

function localSampleFor(event) {
  return state.localSamples.get(realizationKey(event)) || null;
}

function packBindingFor(event) {
  return state.soundPackDoc ? resolveBinding(state.soundPackDoc, event) : null;
}

function effectiveRealization(event) {
  const local = localSampleFor(event);
  if (local) return {kind: "sample", origin: "local", name: local.file.name, file: local.file, gain: 1, loop: local.loop, root_note: local.root_note || null};
  const binding = packBindingFor(event);
  if (!binding) return {kind: "reference", origin: "reference", name: "Reference synth"};
  const key = fileKeyFor(state.soundPackManifestPath, binding.asset);
  const file = state.soundPackFiles.get(key);
  if (!file) return {kind: "reference", origin: "missing", name: "Reference synth", missing: binding.asset};
  return {kind: "sample", origin: "pack", name: binding.asset, file, gain: binding.gain ?? 1, loop: Boolean(binding.loop), root_note: binding.root_note || null, credit: binding.credit || ""};
}

function packAvailability() {
  if (!state.soundPackDoc) return {bindings: 0, missing: 0};
  let missing = 0;
  for (const binding of state.soundPackDoc.bindings) {
    const key = fileKeyFor(state.soundPackManifestPath, binding.asset);
    if (!state.soundPackFiles.has(key)) missing++;
  }
  return {bindings: state.soundPackDoc.bindings.length, missing};
}

function renderPackSettings() {
  if (!state.soundPackDoc) return;
  const availability = packAvailability();
  $("pack-name").textContent = state.soundPackDoc.name;
  const detail = describePack(state.soundPackDoc);
  $("pack-meta").textContent = availability.bindings
    ? `${detail} · ${availability.bindings - availability.missing}/${availability.bindings} samples available; missing samples fall back.`
    : `${detail} · ${state.soundPackDoc.provenance.notes || "Reference playback."}`;
}

function useReferenceSoundPack() {
  state.soundPackDoc = structuredClone(state.referenceSoundPackDoc);
  state.soundPackManifestPath = "soundpacks/reference.json";
  state.soundPackFiles = new Map();
  renderAll();
  status("Using the Reference Synth pack. Local sample overrides still take priority.");
}

async function loadSoundPackFolder(fileList) {
  const files = [...fileList];
  let manifestFile = null;
  let parsed = null;
  for (const file of files.filter(candidate => candidate.name.toLowerCase().endsWith(".json"))) {
    try {
      const candidate = JSON.parse(await file.text());
      if (candidate?.format === "esn-sound-pack/1") {
        manifestFile = file;
        parsed = candidate;
        break;
      }
    } catch (_) {
      // Ignore unrelated JSON files while looking for a pack manifest.
    }
  }
  if (!manifestFile) throw new Error("No esn-sound-pack/1 manifest was found in that folder.");
  const doc = validatePack(parsed, state.registryDoc, noteToMidi);
  const manifestPath = (manifestFile.webkitRelativePath || manifestFile.name).replaceAll("\\", "/");
  const fileMap = new Map(files.map(file => [(file.webkitRelativePath || file.name).replaceAll("\\", "/"), file]));
  state.soundPackDoc = doc;
  state.soundPackManifestPath = manifestPath;
  state.soundPackFiles = fileMap;
  renderAll();
  const availability = packAvailability();
  status(`Loaded ${doc.name}: ${availability.bindings - availability.missing}/${availability.bindings} sample bindings available; ${availability.missing} use reference fallback.`);
}

const SCORE_FIELDS = new Set(["format", "title", "tempo_bpm", "metadata", "events"]);
const EVENT_FIELDS = new Set(["id", "source", "gesture", "onset", "duration", "pitch", "dynamics", "articulation", "pitch_curve"]);
const ARTICULATIONS = new Set(["normal", "staccato", "tenuto", "accent", "legato"]);

function finiteNumber(value, label, minimum = null) {
  if (typeof value !== "number" || !Number.isFinite(value) || (minimum !== null && value < minimum)) {
    throw new Error(`${label} is not a valid number.`);
  }
  return value;
}

function validatePitch(pitch, label) {
  if (!pitch || typeof pitch !== "object" || Array.isArray(pitch)) throw new Error(`${label} must be a pitch object.`);
  const keys = Object.keys(pitch);
  if (keys.length !== 1 || !["note", "hz"].includes(keys[0])) throw new Error(`${label} must contain exactly note or hz.`);
  if (keys[0] === "note") {
    if (typeof pitch.note !== "string" || noteToMidi(pitch.note) === null) throw new Error(`${label} has an invalid note.`);
  } else {
    finiteNumber(pitch.hz, `${label}.hz`, Number.MIN_VALUE);
  }
}

function validateProject(score) {
  if (!score || typeof score !== "object" || Array.isArray(score)) throw new Error("Project root must be an object.");
  const unknownScore = Object.keys(score).filter(key => !SCORE_FIELDS.has(key));
  if (unknownScore.length) throw new Error(`Project contains unknown fields: ${unknownScore.join(", ")}.`);
  if (score.format !== "esn/1") throw new Error("Project format must be esn/1.");
  if (typeof score.title !== "string" || !score.title.trim()) throw new Error("Project title cannot be empty.");
  finiteNumber(score.tempo_bpm ?? 120, "tempo_bpm", 1);
  if ("metadata" in score && (!score.metadata || typeof score.metadata !== "object" || Array.isArray(score.metadata))) throw new Error("Project metadata must be an object.");
  if (!Array.isArray(score.events)) throw new Error("Project events must be an array.");

  const ids = new Set();
  score.events.forEach((event, index) => {
    const where = `Event ${index + 1}`;
    if (!event || typeof event !== "object" || Array.isArray(event)) throw new Error(`${where} must be an object.`);
    const unknown = Object.keys(event).filter(key => !EVENT_FIELDS.has(key));
    if (unknown.length) throw new Error(`${where} contains unknown fields: ${unknown.join(", ")}.`);
    if (typeof event.id !== "string" || !event.id) throw new Error(`${where} needs an ID.`);
    if (ids.has(event.id)) throw new Error(`Duplicate event ID: ${event.id}.`);
    ids.add(event.id);
    const source = state.sources.get(event.source);
    if (!source) throw new Error(`${where} uses an unknown sound source: ${event.source}.`);
    if (!source.gestures.includes(event.gesture)) throw new Error(`${where} uses an invalid action for ${sourceLabel(event.source)}.`);
    finiteNumber(event.onset, `${where} onset`, 0);
    finiteNumber(event.duration, `${where} duration`, 0.000001);
    const dynamics = finiteNumber(event.dynamics ?? 0.75, `${where} loudness`, 0);
    if (dynamics > 1) throw new Error(`${where} loudness must be between 0 and 1.`);
    if (!ARTICULATIONS.has(event.articulation ?? "normal")) throw new Error(`${where} has an unknown articulation.`);
    if (source.pitch_policy === "required" && !event.pitch) throw new Error(`${where} requires a pitch.`);
    if (source.pitch_policy === "forbidden" && event.pitch) throw new Error(`${where} cannot have a pitch.`);
    if (event.pitch) validatePitch(event.pitch, `${where} pitch`);
    if (event.pitch_curve !== undefined) {
      if (!event.pitch) throw new Error(`${where} pitch curve needs a starting pitch.`);
      if (!Array.isArray(event.pitch_curve) || !event.pitch_curve.length) throw new Error(`${where} pitch curve must contain points.`);
      let previous = -1;
      event.pitch_curve.forEach((point, pointIndex) => {
        if (!point || typeof point !== "object" || Array.isArray(point) || Object.keys(point).sort().join(",") !== "at,pitch") throw new Error(`${where} pitch curve point ${pointIndex + 1} is invalid.`);
        finiteNumber(point.at, `${where} pitch curve position`, 0);
        if (point.at > 1 || point.at <= previous) throw new Error(`${where} pitch curve positions must increase within 0..1.`);
        previous = point.at;
        validatePitch(point.pitch, `${where} pitch curve point ${pointIndex + 1}`);
      });
    }
  });
  return score;
}

function applyScore(score, message) {
  validateProject(score);
  state.score = structuredClone(score);
  if (!("tempo_bpm" in state.score)) state.score.tempo_bpm = 120;
  state.selectedId = null;
  renderAll();
  status(message);
}

function newScene() {
  applyScore({format: "esn/1", title: "Untitled sound scene", tempo_bpm: 120, events: []}, "New empty sound scene ready.");
}

async function resetExample() {
  const score = await fetch("../examples/first-score.esn.json").then(response => response.json());
  applyScore(score, `Example restored: ${score.events.length} sounds at ${score.tempo_bpm} BPM.`);
}

async function openProjectFile(file) {
  try {
    const parsed = JSON.parse(await file.text());
    applyScore(parsed, `Opened ${file.name}: ${parsed.events.length} sounds at ${parsed.tempo_bpm ?? 120} BPM.`);
  } catch (error) {
    status(`Could not open project: ${error.message}`);
  }
}

function renderSceneSettings() {
  if (!state.score) return;
  $("scene-title").value = state.score.title;
  $("scene-tempo").value = state.score.tempo_bpm ?? 120;
}

function commitSceneSettings() {
  const title = $("scene-title").value.trim();
  const tempo = Number($("scene-tempo").value);
  if (!title) {
    $("scene-title").value = state.score.title;
    return status("Scene title cannot be empty.");
  }
  if (!Number.isFinite(tempo) || tempo < 1) {
    $("scene-tempo").value = state.score.tempo_bpm ?? 120;
    return status("Tempo must be at least 1 BPM.");
  }
  state.score.title = title;
  state.score.tempo_bpm = tempo;
  status(`Scene updated: ${title} at ${tempo} BPM.`);
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
  renderSceneSettings();
  renderPackSettings();
  renderVisualMode();
  renderPalette();
  renderRuler();
  renderTimeline();
  renderInspector();
}

function renderVisualMode() {
  $("color-mode").value = state.colorMode;
  const mode = state.colorMode === "pitch_class"
    ? "same note name = same color"
    : `scale steps relative to ${state.visualDoc.scale.tonic}`;
  $("color-legend").textContent = `colors: ${mode}`;
}

function renderPalette() {
  const root = $("palette");
  root.replaceChildren();
  for (const source of state.registryDoc.sources) {
    const group = document.createElement("div");
    group.className = "source-group";
    group.innerHTML = `<div class="source-name" title="${source.id}">${sourceGlyph(source.id, state.visualDoc.palettes.unpitched, 22)}<span>${sourceLabel(source.id)}</span></div>`;
    const gestures = document.createElement("div");
    gestures.className = "gesture-list";
    for (const gesture of source.gestures) {
      const button = document.createElement("button");
      button.className = "gesture-button";
      button.textContent = actionLabel(gesture);
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
    label.textContent = sourceLabel(source);
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
    chip.innerHTML = `<span class="glyph">${sourceGlyph(event.source, color, 22)}</span><span class="meta">${actionLabel(event.gesture)}${event.pitch?.note ? ` · ${event.pitch.note}` : ""}</span>`;
    chip.title = `${sourceLabel(event.source)} · ${actionLabel(event.gesture)} · ${cue}`;
    chip.addEventListener("click", e => {
      e.stopPropagation();
      state.selectedId = event.id;
      renderAll();
    });
    installDrag(chip, event);
    root.append(chip);
  }

  root.onclick = click => {
    if (click.target !== root) return;
    if (state.ignoreTimelineClick) {
      state.ignoreTimelineClick = false;
      return;
    }
    state.selectedId = null;
    renderAll();
  };
}

function installDrag(element, event) {
  element.addEventListener("pointerdown", down => {
    down.stopPropagation();
    element.setPointerCapture(down.pointerId);
    const startX = down.clientX;
    const startY = down.clientY;
    const originalOnset = Number(event.onset);
    const originalMidi = pitchMidi(event);
    let moved = false;

    const move = current => {
      const deltaX = current.clientX - startX;
      const deltaY = current.clientY - startY;
      if (!moved && Math.abs(deltaX) < 3 && Math.abs(deltaY) < 3) return;
      moved = true;
      const beats = Math.round((deltaX / PX_PER_BEAT) * 4) / 4;
      event.onset = Math.max(0, originalOnset + beats);
      if (originalMidi !== null) {
        const semitones = Math.round(-deltaY / SEMITONE_PX);
        event.pitch = {note: midiToNote(originalMidi + semitones)};
        delete event.pitch_curve;
      }
      element.style.left = `${event.onset * PX_PER_BEAT}px`;
      element.style.top = `${eventTop(event)}px`;
    };
    const up = () => {
      element.removeEventListener("pointermove", move);
      if (!moved) return;
      state.selectedId = event.id;
      state.ignoreTimelineClick = true;
      setTimeout(() => { state.ignoreTimelineClick = false; }, 0);
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
  status(`Added ${sourceLabel(source.id)}: ${actionLabel(gesture)}.`);
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
  $("event-source").value = sourceLabel(event.source);
  $("event-onset").value = event.onset;
  $("event-duration").value = event.duration;
  $("event-dynamics").value = event.dynamics ?? 0.75;
  $("pitch-row").hidden = source.pitch_policy === "forbidden";
  $("event-pitch").value = event.pitch?.note || "";
  const gestureSelect = $("event-gesture");
  gestureSelect.replaceChildren(...source.gestures.map(gesture => new Option(actionLabel(gesture), gesture)));
  gestureSelect.value = event.gesture;
  const local = localSampleFor(event);
  const realization = effectiveRealization(event);
  if (realization.kind === "sample") {
    $("event-realization").textContent = realization.origin === "local" ? `Local sample · ${realization.name}` : `${state.soundPackDoc.name} · ${realization.name}`;
    $("event-realization-detail").textContent = realization.credit || (realization.origin === "local" ? "Applies to every matching source/action in this session." : `Pack sample · ${state.soundPackDoc.license.name}`);
  } else {
    $("event-realization").textContent = realization.missing ? "Reference synth · sample missing" : "Reference synth";
    $("event-realization-detail").textContent = realization.missing ? `Could not find ${realization.missing}; playback falls back safely.` : "Uses the built-in sketch sound.";
  }
  $("sample-loop").checked = Boolean(local?.loop);
  $("sample-root").value = local?.root_note || "";
  $("sample-loop").disabled = !local;
  $("sample-root").disabled = !local;
  $("clear-sample").disabled = !local;
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

function setLocalSample(file) {
  const event = selectedEvent();
  if (!event) return;
  state.localSamples.set(realizationKey(event), {file, loop: false, root_note: null});
  renderInspector();
  status(`Using ${file.name} for ${sourceLabel(event.source)}: ${actionLabel(event.gesture)} in this session.`);
}

function commitLocalSampleSettings() {
  const event = selectedEvent();
  if (!event) return;
  const local = localSampleFor(event);
  if (!local) return;
  const rootNote = $("sample-root").value.trim();
  if (rootNote && noteToMidi(rootNote) === null) {
    $("sample-root").value = local.root_note || "";
    return status(`Invalid sample root pitch: ${rootNote}`);
  }
  local.loop = $("sample-loop").checked;
  local.root_note = rootNote || null;
  renderInspector();
  status(`Updated local sample realization for ${sourceLabel(event.source)}: ${actionLabel(event.gesture)}.`);
}

function audioContext() {
  if (!state.audio) state.audio = new (window.AudioContext || window.webkitAudioContext)();
  return state.audio;
}

function midiHz(midi) {
  return 440 * 2 ** ((midi - 69) / 12);
}

function previewReferenceEvent(event, when = null, durationOverride = null) {
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

async function decodedSample(file) {
  if (!state.sampleBuffers.has(file)) {
    const ctx = audioContext();
    const promise = file.arrayBuffer().then(data => ctx.decodeAudioData(data.slice(0)));
    state.sampleBuffers.set(file, promise);
  }
  return state.sampleBuffers.get(file);
}

function samplePlaybackRate(event, rootNote, midiOverride = null) {
  if (!rootNote) return 1;
  const rootMidi = noteToMidi(rootNote);
  const midi = midiOverride ?? pitchMidi(event);
  if (rootMidi === null || midi === null) return 1;
  return 2 ** ((midi - rootMidi) / 12);
}

async function prepareRealization(event) {
  const realization = effectiveRealization(event);
  if (realization.kind !== "sample") return realization;
  try {
    return {...realization, buffer: await decodedSample(realization.file)};
  } catch (error) {
    return {kind: "reference", origin: "decode-fallback", name: "Reference synth", failure: error.message};
  }
}

function previewSampleEvent(event, realization, start, duration) {
  const ctx = audioContext();
  const source = ctx.createBufferSource();
  const gainNode = ctx.createGain();
  source.buffer = realization.buffer;
  source.loop = Boolean(realization.loop);
  gainNode.gain.setValueAtTime((realization.gain ?? 1) * (event.dynamics ?? 0.75), start);
  source.playbackRate.setValueAtTime(samplePlaybackRate(event, realization.root_note), start);
  for (const point of event.pitch_curve || []) {
    const pointMidi = point.pitch.note ? noteToMidi(point.pitch.note) : 69 + 12 * Math.log2(point.pitch.hz / 440);
    const rate = Math.max(0.01, samplePlaybackRate(event, realization.root_note, pointMidi));
    source.playbackRate.exponentialRampToValueAtTime(rate, start + point.at * duration);
  }
  source.connect(gainNode);
  gainNode.connect(ctx.destination);
  source.start(start);
  source.stop(start + duration);
}

async function previewEvent(event, when = null, durationOverride = null, prepared = null) {
  const ctx = audioContext();
  const start = when ?? ctx.currentTime + 0.02;
  const beatSeconds = 60 / Number(state.score.tempo_bpm || 120);
  const duration = durationOverride ?? Number(event.duration) * beatSeconds;
  const realization = prepared || await prepareRealization(event);
  if (realization.kind === "sample") previewSampleEvent(event, realization, start, duration);
  else previewReferenceEvent(event, start, duration);
  return realization;
}

async function playScore() {
  const ctx = audioContext();
  const beatSeconds = 60 / Number(state.score.tempo_bpm || 120);
  const prepared = await Promise.all(state.score.events.map(prepareRealization));
  const base = ctx.currentTime + 0.08;
  state.score.events.forEach((event, index) => previewEvent(event, base + Number(event.onset) * beatSeconds, null, prepared[index]));
  const sampleCount = prepared.filter(item => item.kind === "sample").length;
  const fallbackCount = prepared.length - sampleCount;
  status(`Previewing ${prepared.length} sounds: ${sampleCount} sample-backed, ${fallbackCount} reference synth.`);
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  }
  return value;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function exportScore() {
  const text = JSON.stringify(canonical(state.score), null, 2) + "\n";
  downloadBlob(new Blob([text], {type: "application/json"}), "sound-scene.esn.json");
  status("Saved editable ESN project.");
}

function exportCueSheet() {
  const text = cueCsv(state.score, state.interchangeDoc, noteToMidi);
  downloadBlob(new Blob([text], {type: "text/csv;charset=utf-8"}), "sound-scene-cues.csv");
  status(`Cue sheet ready: ${state.score.events.length} sounds with beat positions and timecodes.`);
}

function exportMidi() {
  const {bytes, report} = midiBytes(state.score, state.interchangeDoc, noteToMidi);
  downloadBlob(new Blob([bytes], {type: "audio/midi"}), "sound-scene.mid");
  status(`MIDI ready: ${report.midi_notes} playable notes, ${report.cue_only} cue-only sounds, all ${report.events_total} preserved as timed ESN cues.`);
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
  const meaning = state.colorMode === "pitch_class" ? "note names" : `scale steps relative to ${state.visualDoc.scale.tonic}`;
  status(`Colors now show ${meaning}.`);
});
$("load-pack").addEventListener("click", () => $("pack-folder").click());
$("pack-folder").addEventListener("change", async event => {
  const files = event.target.files;
  if (files?.length) {
    try { await loadSoundPackFolder(files); }
    catch (error) { status(`Could not load sound pack: ${error.message}`); }
  }
  event.target.value = "";
});
$("use-reference-pack").addEventListener("click", useReferenceSoundPack);
$("choose-sample").addEventListener("click", () => $("sample-file").click());
$("sample-file").addEventListener("change", event => {
  const file = event.target.files?.[0];
  if (file) setLocalSample(file);
  event.target.value = "";
});
$("sample-loop").addEventListener("change", commitLocalSampleSettings);
$("sample-root").addEventListener("change", commitLocalSampleSettings);
$("clear-sample").addEventListener("click", () => {
  const event = selectedEvent();
  if (!event) return;
  state.localSamples.delete(realizationKey(event));
  renderInspector();
  status(`Cleared local sample for ${sourceLabel(event.source)}: ${actionLabel(event.gesture)}.`);
});
$("new-scene").addEventListener("click", newScene);
$("open-project").addEventListener("click", () => $("project-file").click());
$("project-file").addEventListener("change", async event => {
  const file = event.target.files?.[0];
  if (file) await openProjectFile(file);
  event.target.value = "";
});
$("scene-title").addEventListener("change", commitSceneSettings);
$("scene-tempo").addEventListener("change", commitSceneSettings);
$("reload").addEventListener("click", () => resetExample());
$("play-score").addEventListener("click", playScore);
$("export").addEventListener("click", exportScore);
$("export-cues").addEventListener("click", exportCueSheet);
$("export-midi").addEventListener("click", exportMidi);
$("play-event").addEventListener("click", async () => {
  const event = selectedEvent();
  if (!event) return;
  const realization = await previewEvent(event);
  const via = realization.kind === "sample" ? realization.name : "Reference synth";
  status(`Previewing ${sourceLabel(event.source)}: ${actionLabel(event.gesture)} via ${via}.`);
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
