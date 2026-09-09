"use strict";

(function exposeEsnInterchangeDomain(root) {
  function halfUp(value) { return Math.floor(value + 0.5); }

  function pitchMidi(event, noteToMidi) {
    if (!event.pitch) return null;
    if (typeof event.pitch.note === "string") return noteToMidi(event.pitch.note);
    if (typeof event.pitch.hz === "number" && Number.isFinite(event.pitch.hz) && event.pitch.hz > 0) {
      return 69 + 12 * Math.log2(event.pitch.hz / 440);
    }
    return null;
  }

  function mappingFor(event, profile) {
    return profile.midi_sources.find(mapping => mapping.source === event.source) || null;
  }

  function eventMapping(event, profile, noteToMidi) {
    const mapping = mappingFor(event, profile);
    if (!mapping) return {mapping: null, note: null, losses: ["cue_only"]};
    let note = null;
    if (mapping.mode === "fixed") note = mapping.note;
    else {
      const midi = pitchMidi(event, noteToMidi);
      if (midi === null) return {mapping, note: null, losses: ["pitch_required"]};
      note = Math.max(0, Math.min(127, halfUp(midi)));
    }
    const losses = event.pitch_curve?.length ? ["pitch_curve_flattened"] : [];
    return {mapping, note, losses};
  }
  function classification(event, profile, noteToMidi) {
    const {mapping, note, losses} = eventMapping(event, profile, noteToMidi);
    if (!mapping) return {status: "cue_only", channel: "", note: ""};
    if (note === null) return {status: losses[0] || "pitch_required", channel: mapping.channel + 1, note: ""};
    const suffix = losses.length ? `:${losses.join("+")}` : "";
    return {status: `midi_note${suffix}`, channel: mapping.channel + 1, note};
  }

  function cueRows(score, profile, noteToMidi) {
    const beatSeconds = 60 / Number(score.tempo_bpm || 120);
    return [...score.events]
      .sort((a, b) => Number(a.onset) - Number(b.onset) || a.id.localeCompare(b.id))
      .map(event => {
        const onset = Number(event.onset);
        const duration = Number(event.duration);
        const mapped = classification(event, profile, noteToMidi);
        let pitch = "";
        if (event.pitch?.note) pitch = `note:${event.pitch.note}`;
        else if (typeof event.pitch?.hz === "number") pitch = `hz:${event.pitch.hz}`;
        return {
          id: event.id, source: event.source, gesture: event.gesture,
          onset_beats: String(onset), end_beats: String(onset + duration),
          start_seconds: (onset * beatSeconds).toFixed(6),
          end_seconds: ((onset + duration) * beatSeconds).toFixed(6),
          duration_seconds: (duration * beatSeconds).toFixed(6),
          pitch, dynamics: String(event.dynamics ?? 0.75),
          articulation: event.articulation ?? "normal",
          midi_status: mapped.status, midi_channel: String(mapped.channel), midi_note: String(mapped.note),
        };
      });
  }
  function escapeCsv(value) {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  }

  function cueCsv(score, profile, noteToMidi) {
    const fields = [
      "id", "source", "gesture", "onset_beats", "end_beats",
      "start_seconds", "end_seconds", "duration_seconds", "pitch",
      "dynamics", "articulation", "midi_status", "midi_channel", "midi_note",
    ];
    const lines = [fields.join(",")];
    for (const row of cueRows(score, profile, noteToMidi)) {
      lines.push(fields.map(field => escapeCsv(row[field])).join(","));
    }
    return lines.join("\n") + "\n";
  }

  function concatBytes(...parts) {
    const arrays = parts.map(part => part instanceof Uint8Array ? part : Uint8Array.from(part));
    const total = arrays.reduce((sum, part) => sum + part.length, 0);
    const out = new Uint8Array(total);
    let offset = 0;
    for (const part of arrays) { out.set(part, offset); offset += part.length; }
    return out;
  }

  function u16(value) { return Uint8Array.of((value >>> 8) & 255, value & 255); }
  function u32(value) { return Uint8Array.of((value >>> 24) & 255, (value >>> 16) & 255, (value >>> 8) & 255, value & 255); }
  function vlq(value) {
    if (!Number.isInteger(value) || value < 0 || value > 0x0fffffff) throw new Error("MIDI VLQ out of range");
    let buffer = value & 0x7f;
    const out = [buffer];
    while ((value >>= 7)) {
      buffer = (value & 0x7f) | 0x80;
      out.unshift(buffer);
    }
    return Uint8Array.from(out);
  }

  function asciiBytes(text) {
    let escaped = "";
    for (const ch of String(text)) {
      const cp = ch.codePointAt(0);
      if (cp <= 0x7f) escaped += ch;
      else if (cp <= 0xffff) escaped += `\\u${cp.toString(16).padStart(4, "0")}`;
      else {
        const value = cp - 0x10000;
        const high = 0xd800 + (value >> 10);
        const low = 0xdc00 + (value & 0x3ff);
        escaped += `\\u${high.toString(16)}\\u${low.toString(16)}`;
      }
    }
    return Uint8Array.from([...escaped].map(ch => ch.charCodeAt(0)));
  }

  function meta(kind, payload) {
    return concatBytes([0xff, kind], vlq(payload.length), payload);
  }
  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object") {
      return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
    }
    return value;
  }

  function asciiJson(value) {
    return new TextDecoder("ascii").decode(asciiBytes(JSON.stringify(canonical(value))));
  }

  function byteCompare(a, b) {
    const limit = Math.min(a.length, b.length);
    for (let i = 0; i < limit; i++) if (a[i] !== b[i]) return a[i] - b[i];
    return a.length - b.length;
  }

  function track(events) {
    const ordered = [...events].sort((a, b) => a.tick - b.tick || a.priority - b.priority || byteCompare(a.message, b.message));
    const payload = [];
    let previous = 0;
    for (const event of ordered) {
      payload.push(vlq(event.tick - previous), event.message);
      previous = event.tick;
    }
    payload.push(vlq(0), meta(0x2f, new Uint8Array()));
    const body = concatBytes(...payload);
    return concatBytes(asciiBytes("MTrk"), u32(body.length), body);
  }
  function midiBytes(score, profile, noteToMidi) {
    const tpq = Number(profile.ticks_per_quarter);
    const tempoBpm = Number(score.tempo_bpm || 120);
    const tempoUs = halfUp(60000000 / tempoBpm);
    const conductor = [
      {tick: 0, priority: 0, message: meta(0x03, asciiBytes(score.title))},
      {tick: 0, priority: 1, message: meta(0x51, Uint8Array.of((tempoUs >> 16) & 255, (tempoUs >> 8) & 255, tempoUs & 255))},
    ];
    const cueEvents = [{tick: 0, priority: 0, message: meta(0x03, asciiBytes("ESN Semantic Cues"))}];
    const sourceTracks = new Map();
    const reportEvents = [];

    for (const event of score.events) {
      const onsetTick = halfUp(Number(event.onset) * tpq);
      const durationTick = Math.max(1, halfUp(Number(event.duration) * tpq));
      const cue = asciiBytes(profile.cue_prefix + asciiJson(event));
      cueEvents.push({tick: onsetTick, priority: 10, message: meta(0x07, cue)});
      const {mapping, note, losses} = eventMapping(event, profile, noteToMidi);
      const row = {id: event.id, status: "cue_only", losses: [...losses]};
      if (mapping) row.channel = mapping.channel;
      if (mapping && note !== null) {
        row.status = "midi_note";
        row.note = note;
        const channel = Number(mapping.channel);
        const velocity = Math.max(1, Math.min(127, halfUp(Number(event.dynamics ?? 0.75) * 127)));
        if (!sourceTracks.has(event.source)) {
          sourceTracks.set(event.source, [{tick: 0, priority: 0, message: meta(0x03, asciiBytes(event.source))}]);
        }
        const events = sourceTracks.get(event.source);
        if (events.length === 1 && Object.hasOwn(mapping, "program")) {
          events.push({tick: 0, priority: 5, message: Uint8Array.of(0xc0 | channel, Number(mapping.program))});
        }
        events.push({tick: onsetTick, priority: 30, message: Uint8Array.of(0x90 | channel, note, velocity)});
        events.push({tick: onsetTick + durationTick, priority: 20, message: Uint8Array.of(0x80 | channel, note, 0)});
      }
      reportEvents.push(row);
    }

    const tracks = [track(conductor)];
    for (const source of [...sourceTracks.keys()].sort()) tracks.push(track(sourceTracks.get(source)));
    tracks.push(track(cueEvents));
    const header = concatBytes(asciiBytes("MThd"), u32(6), u16(1), u16(tracks.length), u16(tpq));
    const bytes = concatBytes(header, ...tracks);
    const report = {
      format: "esn-midi-report/1",
      events_total: reportEvents.length,
      midi_notes: reportEvents.filter(row => row.status === "midi_note").length,
      cue_only: reportEvents.filter(row => row.status === "cue_only").length,
      events: reportEvents,
    };
    return {bytes, report};
  }

  const api = {classification, cueRows, cueCsv, midiBytes};
  root.EsnInterchangeDomain = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
