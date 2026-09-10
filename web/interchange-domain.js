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

  function midiPlan(score, profile, noteToMidi) {
    const reserved = new Set(profile.midi_sources.map(mapping => Number(mapping.channel)));
    const auxiliaries = Array.from({length:16}, (_, channel) => channel).filter(channel => !reserved.has(channel) && channel !== 9);
    const auxiliaryPrograms = new Map();
    const activeUntil = new Map();
    const tpq = Number(profile.ticks_per_quarter);
    const entries = score.events.map((event, index) => {
      const {mapping, note, losses} = eventMapping(event, profile, noteToMidi);
      const onsetTick = halfUp(Number(event.onset) * tpq);
      const durationTick = Math.max(1, halfUp(Number(event.duration) * tpq));
      return {event, index, mapping, note, losses:[...losses], onsetTick, durationTick};
    }).sort((a,b) => a.onsetTick - b.onsetTick || a.index - b.index);
    const plan = new Map();
    const activeKey = (channel, note) => `${channel}/${note}`;
    for (const entry of entries) {
      let channel = null;
      if (entry.mapping && entry.note !== null) {
        const base = Number(entry.mapping.channel);
        const endTick = entry.onsetTick + entry.durationTick;
        if ((activeUntil.get(activeKey(base, entry.note)) ?? -1) <= entry.onsetTick) channel = base;
        else if (Object.hasOwn(entry.mapping, "program") && base !== 9) {
          const program = Number(entry.mapping.program);
          for (const candidate of auxiliaries) {
            const owner = auxiliaryPrograms.get(candidate);
            if (owner !== undefined && owner !== program) continue;
            if ((activeUntil.get(activeKey(candidate, entry.note)) ?? -1) > entry.onsetTick) continue;
            auxiliaryPrograms.set(candidate, program);
            channel = candidate;
            entry.losses.push("overlap_channel_reassigned");
            break;
          }
        }
        if (channel === null) entry.losses.push("same_note_overlap_cue_only");
        else activeUntil.set(activeKey(channel, entry.note), endTick);
      }
      plan.set(entry.event.id, {...entry, channel});
    }
    return plan;
  }

  function cueRows(score, profile, noteToMidi) {
    const beatSeconds = 60 / Number(score.tempo_bpm || 120);
    const plan = midiPlan(score, profile, noteToMidi);
    return [...score.events]
      .sort((a, b) => Number(a.onset) - Number(b.onset) || a.id.localeCompare(b.id))
      .map(event => {
        const onset = Number(event.onset);
        const duration = Number(event.duration);
        const planned = plan.get(event.id);
        let midiStatus;
        if (planned.mapping && planned.note !== null && planned.channel !== null) {
          midiStatus = `midi_note${planned.losses.length ? `:${planned.losses.join("+")}` : ""}`;
        } else if (planned.losses.includes("same_note_overlap_cue_only")) midiStatus = "cue_only:same_note_overlap_cue_only";
        else midiStatus = planned.losses[0] || "cue_only";
        const midiChannel = planned.mapping ? (planned.channel ?? Number(planned.mapping.channel)) + 1 : "";
        const midiNote = planned.note ?? "";
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
          midi_status: midiStatus, midi_channel: String(midiChannel), midi_note: String(midiNote),
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
    const programmedChannels = new Set();
    const reportEvents = [];
    const plan = midiPlan(score, profile, noteToMidi);

    for (const event of score.events) {
      const planned = plan.get(event.id);
      const onsetTick = planned.onsetTick;
      const durationTick = planned.durationTick;
      const cue = asciiBytes(profile.cue_prefix + asciiJson(event));
      cueEvents.push({tick: onsetTick, priority: 10, message: meta(0x07, cue)});
      const {mapping, note, losses, channel} = planned;
      const row = {id: event.id, status: "cue_only", losses: [...losses]};
      if (mapping) row.channel = channel === null ? Number(mapping.channel) : channel;
      if (mapping && note !== null && channel !== null) {
        row.status = "midi_note";
        row.note = note;
        const velocity = Math.max(1, Math.min(127, halfUp(Number(event.dynamics ?? 0.75) * 127)));
        if (!sourceTracks.has(event.source)) {
          sourceTracks.set(event.source, [{tick: 0, priority: 0, message: meta(0x03, asciiBytes(event.source))}]);
        }
        const events = sourceTracks.get(event.source);
        const programKey = `${event.source}/${channel}`;
        if (Object.hasOwn(mapping, "program") && !programmedChannels.has(programKey)) {
          events.push({tick: 0, priority: 5, message: Uint8Array.of(0xc0 | channel, Number(mapping.program))});
          programmedChannels.add(programKey);
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

  const api = {classification, cueRows, cueCsv, midiBytes, midiPlan};
  root.EsnInterchangeDomain = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
