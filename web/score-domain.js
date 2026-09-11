"use strict";

(function exposeScoreDomain(root) {
  const TICKS_PER_QUARTER = 9600;
  const DEFAULT_TEMPO_BPM = 96;
  const DEFAULT_A4_HZ = 432;
  const SCALES = new Set(["major","minor","major_pentatonic","minor_pentatonic","chromatic"]);
  const ARTICULATIONS = new Set(["normal","staccato","tenuto","accent","legato"]);
  const CHORD_INTERVALS = {
    major:[0,4,7], minor:[0,3,7], diminished:[0,3,6], augmented:[0,4,8],
    sus2:[0,2,7], sus4:[0,5,7], dominant7:[0,4,7,10], major7:[0,4,7,11],
    minor7:[0,3,7,10], major_pentatonic:[0,2,4,7,9], minor_pentatonic:[0,3,5,7,10],
  };
  const NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];

  function clone(value) { return structuredClone(value); }
  function factoryDefaults() {
    return {tempo_bpm:96,time_signature:{numerator:4,denominator:4},key:{tonic:"C",scale:"major"},tuning:{a4_hz:432}};
  }
  function number(value, label, min = null, max = null) {
    if (typeof value !== "number" || !Number.isFinite(value) || (min !== null && value < min) || (max !== null && value > max)) throw new Error(`${label} is invalid.`);
    return value;
  }
  function integer(value, label, min = null) {
    if (!Number.isInteger(value) || (min !== null && value < min)) throw new Error(`${label} must be an integer${min === null ? "" : ` >= ${min}`}.`);
    return value;
  }
  function requireId(value, label) {
    if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be a non-empty string.`);
    return value;
  }
  function validateTimeSignature(value, label) {
    if (!value || typeof value !== "object" || Array.isArray(value) || Object.keys(value).sort().join(",") !== "denominator,numerator") throw new Error(`${label} must contain numerator and denominator.`);
    integer(value.numerator, `${label}.numerator`, 1);
    integer(value.denominator, `${label}.denominator`, 1);
    if (![1,2,4,8,16,32,64].includes(value.denominator)) throw new Error(`${label}.denominator must be a power-of-two musical denominator.`);
  }
  function validateKey(value, label) {
    if (!value || typeof value !== "object" || Array.isArray(value) || Object.keys(value).sort().join(",") !== "scale,tonic") throw new Error(`${label} must contain tonic and scale.`);
    if (!/^[A-G](?:#|b)?$/.test(value.tonic || "")) throw new Error(`${label}.tonic is invalid.`);
    if (!SCALES.has(value.scale)) throw new Error(`${label}.scale is invalid.`);
  }
  function validateTuning(value, label) {
    if (!value || typeof value !== "object" || Array.isArray(value) || Object.keys(value).join(",") !== "a4_hz") throw new Error(`${label} must contain only a4_hz.`);
    number(value.a4_hz, `${label}.a4_hz`, Number.MIN_VALUE, 20000);
  }
  function validateContext(value, label, complete = false) {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be an object.`);
    const allowed = new Set(["tempo_bpm","time_signature","key","tuning"]);
    const extra = Object.keys(value).filter(key => !allowed.has(key));
    if (extra.length) throw new Error(`${label} has unknown fields: ${extra.join(", ")}.`);
    if (complete && [...allowed].some(key => !(key in value))) throw new Error(`${label} must contain tempo, meter, key and tuning.`);
    if ("tempo_bpm" in value) number(value.tempo_bpm, `${label}.tempo_bpm`, 1);
    if ("time_signature" in value) validateTimeSignature(value.time_signature, `${label}.time_signature`);
    if ("key" in value) validateKey(value.key, `${label}.key`);
    if ("tuning" in value) validateTuning(value.tuning, `${label}.tuning`);
  }
  function resolveContext(defaults, trackContext = {}, sectionContext = {}) {
    return Object.assign(clone(defaults), clone(trackContext), clone(sectionContext));
  }
  function midiToNote(midi) {
    if (!Number.isInteger(midi) || midi < 0 || midi > 127) throw new Error("expanded chord note is outside MIDI range.");
    return `${NOTE_NAMES[midi % 12]}${Math.floor(midi / 12) - 1}`;
  }
  function expandChordPitches(chord, noteToMidi) {
    const rootMidi = noteToMidi(chord.root);
    if (rootMidi === null) throw new Error("chord root must be a valid note name.");
    const intervals = CHORD_INTERVALS[chord.quality];
    if (!intervals) throw new Error(`unknown chord quality: ${chord.quality}`);
    const inversion = chord.inversion ?? 0;
    if (!Number.isInteger(inversion) || inversion < 0 || inversion >= intervals.length) throw new Error("chord inversion must select a chord voice.");
    const midis = intervals.map(interval => rootMidi + interval);
    for (let index = 0; index < inversion; index++) midis[index] += 12;
    midis.sort((a,b) => a-b);
    if ((chord.voicing ?? "close") === "open" && midis.length >= 3) {
      midis[1] += 12;
      midis.sort((a,b) => a-b);
    }
    return midis.map(midiToNote);
  }
  function pitchToMidiWithTuning(pitch, a4Hz, noteToMidi) {
    if (pitch && Object.keys(pitch).length === 1 && typeof pitch.note === "string") {
      const midi = noteToMidi(pitch.note);
      if (midi === null) throw new Error(`invalid note: ${pitch.note}`);
      return midi;
    }
    if (pitch && Object.keys(pitch).length === 1 && typeof pitch.hz === "number" && pitch.hz > 0) return 69 + 12 * Math.log2(pitch.hz / a4Hz);
    throw new Error("pitch must contain exactly note or hz.");
  }
  function midiToHzWithTuning(midi, a4Hz) { return a4Hz * 2 ** ((midi - 69) / 12); }
  function validatePitch(pitch, label, noteToMidi) {
    if (!pitch || typeof pitch !== "object" || Array.isArray(pitch) || Object.keys(pitch).length !== 1) throw new Error(`${label} must contain exactly note or hz.`);
    if ("note" in pitch) {
      if (typeof pitch.note !== "string" || noteToMidi(pitch.note) === null) throw new Error(`${label} has an invalid note.`);
    } else if ("hz" in pitch) number(pitch.hz, `${label}.hz`, Number.MIN_VALUE);
    else throw new Error(`${label} must contain exactly note or hz.`);
  }
  function validateObject(obj, source, section, label, noteToMidi) {
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) throw new Error(`${label} must be an object.`);
    requireId(obj.id, `${label}.id`);
    if (!["note","event","chord"].includes(obj.type)) throw new Error(`${label}.type is invalid.`);
    if (!source.gestures.includes(obj.gesture)) throw new Error(`${label}.gesture is invalid for ${source.id}.`);
    integer(obj.tick, `${label}.tick`, 0); integer(obj.duration_ticks, `${label}.duration_ticks`, 1);
    if (obj.tick < section.start_tick || obj.tick + obj.duration_ticks > section.end_tick) throw new Error(`${label} must fit within its section.`);
    number(obj.dynamics ?? .75, `${label}.dynamics`, 0, 1);
    if (!ARTICULATIONS.has(obj.articulation ?? "normal")) throw new Error(`${label}.articulation is invalid.`);
    if (obj.type === "chord") {
      if (source.pitch_policy === "forbidden") throw new Error(`${label} cannot be a chord for ${source.id}.`);
      expandChordPitches(obj, noteToMidi);
      if (!["close","open"].includes(obj.voicing ?? "close")) throw new Error(`${label}.voicing is invalid.`);
      if (obj.arpeggiation) {
        if (!["up","down"].includes(obj.arpeggiation.direction)) throw new Error(`${label}.arpeggiation direction is invalid.`);
        integer(obj.arpeggiation.step_ticks, `${label}.arpeggiation.step_ticks`, 0);
      }
      return;
    }
    if (obj.type === "note" && !obj.pitch) throw new Error(`${label}.pitch is required for notes.`);
    if (source.pitch_policy === "required" && !obj.pitch) throw new Error(`${label}.pitch is required for ${source.id}.`);
    if (source.pitch_policy === "forbidden" && obj.pitch) throw new Error(`${label}.pitch is forbidden for ${source.id}.`);
    if (obj.pitch) validatePitch(obj.pitch, `${label}.pitch`, noteToMidi);
  }
  function validateScoreV2(score, registryDoc, noteToMidi) {
    if (!score || typeof score !== "object" || Array.isArray(score)) throw new Error("score root must be an object.");
    if (score.format !== "esn/2") throw new Error("score format must be esn/2.");
    if (typeof score.title !== "string" || !score.title.trim()) throw new Error("score title must be non-empty.");
    integer(score.length_ticks, "length_ticks", 1); validateContext(score.defaults, "defaults", true);
    if (!Array.isArray(score.tracks) || !score.tracks.length) throw new Error("tracks must be a non-empty array.");
    const sources = new Map(registryDoc.sources.map(source => [source.id, source]));
    const ids = new Set();
    for (const [trackIndex, track] of score.tracks.entries()) {
      requireId(track.id, `tracks[${trackIndex}].id`);
      if (ids.has(track.id)) throw new Error(`duplicate id: ${track.id}`); ids.add(track.id);
      if (typeof track.name !== "string" || !track.name.trim()) throw new Error(`tracks[${trackIndex}].name must be non-empty.`);
      validateContext(track.context ?? {}, `tracks[${trackIndex}].context`);
      if (!Array.isArray(track.sections) || !track.sections.length) throw new Error(`tracks[${trackIndex}].sections must be non-empty.`);
      let previousEnd = -1;
      for (const [sectionIndex, section] of track.sections.entries()) {
        const label = `tracks[${trackIndex}].sections[${sectionIndex}]`;
        requireId(section.id, `${label}.id`); if (ids.has(section.id)) throw new Error(`duplicate id: ${section.id}`); ids.add(section.id);
        integer(section.start_tick, `${label}.start_tick`, 0); integer(section.end_tick, `${label}.end_tick`, 1);
        if (!(section.start_tick < section.end_tick && section.end_tick <= score.length_ticks)) throw new Error(`${label} must fit within length_ticks.`);
        if (previousEnd > section.start_tick) throw new Error(`${label} overlaps the previous section.`); previousEnd = section.end_tick;
        if (!Array.isArray(section.objects)) throw new Error(`${label}.objects must be an array.`);
        const source = section.source === null ? null : sources.get(section.source);
        if (section.source === null && section.objects.length) throw new Error(`${label}.source is required when the section contains objects.`);
        if (section.source !== null && !source) throw new Error(`${label}.source is not registered: ${section.source}`);
        validateContext(section.context ?? {}, `${label}.context`);
        for (const [objectIndex, obj] of section.objects.entries()) {
          if (obj && ids.has(obj.id)) throw new Error(`duplicate id: ${obj.id}`);
          validateObject(obj, source, section, `${label}.objects[${objectIndex}]`, noteToMidi); ids.add(obj.id);
        }
      }
    }
    return score;
  }
  function findTrack(score, trackId) {
    const track = score.tracks.find(item => item.id === trackId);
    if (!track) throw new Error(`unknown track id: ${trackId}`);
    return track;
  }
  function splitSection(score, trackId, sectionId, splitTick) {
    const result = clone(score); const track = findTrack(result, trackId);
    const index = track.sections.findIndex(section => section.id === sectionId);
    if (index < 0) throw new Error(`unknown section id: ${sectionId}`);
    const section = track.sections[index];
    if (!(section.start_tick < splitTick && splitTick < section.end_tick)) throw new Error("split tick must be inside the section.");
    if (section.objects.some(obj => obj.tick >= splitTick || obj.tick + obj.duration_ticks > splitTick)) throw new Error("split would move or cut existing objects; reposition them first.");
    const used=new Set(result.tracks.flatMap(candidate=>candidate.sections.map(item=>item.id)));
    const base=`${sectionId}-split`; let splitId=base, suffix=2;
    while(used.has(splitId)) splitId=`${base}-${suffix++}`;
    const right = {id:splitId,start_tick:splitTick,end_tick:section.end_tick,source:null,context:clone(section.context ?? {}),objects:[]};
    section.end_tick = splitTick; track.sections.splice(index, 1, section, right); return result;
  }
  function assignSectionSource(score, trackId, sectionId, sourceId, registryDoc) {
    if (!registryDoc.sources.some(source => source.id === sourceId)) throw new Error(`unknown source: ${sourceId}`);
    const result = clone(score); const track = findTrack(result, trackId); const section = track.sections.find(item => item.id === sectionId);
    if (!section) throw new Error(`unknown section id: ${sectionId}`);
    if (section.objects.length) throw new Error("cannot change a populated section source without moving its objects.");
    section.source = sourceId; return result;
  }
  function explodeChord(score, chordId, registryDoc, noteToMidi) {
    const result = clone(score);
    for (const track of result.tracks) for (const section of track.sections) {
      const index = section.objects.findIndex(obj => obj.id === chordId); if (index < 0) continue;
      const chord = section.objects[index]; if (chord.type !== "chord") throw new Error(`${chordId} is not a chord.`);
      const pitches = expandChordPitches(chord, noteToMidi); const arp = chord.arpeggiation;
      const notes = pitches.map((pitch, voice) => {
        const order = !arp || arp.direction === "up" ? voice : pitches.length - voice - 1;
        return {id:`${chordId}-v${voice+1}`,type:"note",gesture:chord.gesture,tick:chord.tick+(arp ? order*arp.step_ticks : 0),duration_ticks:chord.duration_ticks,pitch:{note:pitch},dynamics:chord.dynamics ?? .75,articulation:chord.articulation ?? "normal"};
      });
      section.objects.splice(index, 1, ...notes); validateScoreV2(result, registryDoc, noteToMidi); return result;
    }
    throw new Error(`unknown chord id: ${chordId}`);
  }
  function contextAtTick(score, track, tick) {
    const section = track.sections.find(item => item.start_tick <= tick && tick < item.end_tick);
    return resolveContext(score.defaults, track.context ?? {}, section?.context ?? {});
  }
  function trackTimeAtTick(score, track, tick) {
    if (tick <= 0) return 0;
    tick = Math.min(tick, score.length_ticks);
    const boundaries = new Set([0, tick]);
    for (const section of track.sections) {
      if (section.start_tick > 0 && section.start_tick < tick) boundaries.add(section.start_tick);
      if (section.end_tick > 0 && section.end_tick < tick) boundaries.add(section.end_tick);
    }
    const ordered = [...boundaries].sort((a,b) => a-b); let seconds = 0;
    for (let i=0;i<ordered.length-1;i++) {
      const left=ordered[i], right=ordered[i+1], context=contextAtTick(score,track,left);
      seconds += ((right-left)/TICKS_PER_QUARTER) * (60/context.tempo_bpm);
    }
    return seconds;
  }
  function objectEvents(obj, sourceId, noteToMidi) {
    if (obj.type !== "chord") {
      const event={id:obj.id,source:sourceId,gesture:obj.gesture,tick:obj.tick,duration_ticks:obj.duration_ticks,dynamics:obj.dynamics??.75,articulation:obj.articulation??"normal"};
      if (obj.pitch) event.pitch=clone(obj.pitch); if (obj.pitch_curve) event.pitch_curve=clone(obj.pitch_curve); return [event];
    }
    const pitches=expandChordPitches(obj,noteToMidi), arp=obj.arpeggiation;
    return pitches.map((pitch,index)=>{
      const order=!arp||arp.direction==="up"?index:pitches.length-index-1;
      return {id:`${obj.id}-v${index+1}`,source:sourceId,gesture:obj.gesture,tick:obj.tick+(arp?order*arp.step_ticks:0),duration_ticks:obj.duration_ticks,pitch:{note:pitch},dynamics:obj.dynamics??.75,articulation:obj.articulation??"normal",chord_id:obj.id};
    });
  }
  function flattenScore(score, registryDoc, noteToMidi) {
    validateScoreV2(score, registryDoc, noteToMidi);
    const rows=[];
    for (const track of score.tracks) for (const section of track.sections) {
      const context=resolveContext(score.defaults,track.context??{},section.context??{});
      for (const obj of section.objects) for (const event of objectEvents(obj,section.source,noteToMidi)) {
        const start=trackTimeAtTick(score,track,event.tick);
        const end=trackTimeAtTick(score,track,event.tick+event.duration_ticks);
        const legacy={};
        for (const [key,value] of Object.entries(event)) if (!["tick","duration_ticks","chord_id"].includes(key)) legacy[key]=clone(value);
        legacy.onset=event.tick/TICKS_PER_QUARTER;
        legacy.duration=event.duration_ticks/TICKS_PER_QUARTER;
        rows.push({track_id:track.id,section_id:section.id,object_id:obj.id,object_type:obj.type,event:legacy,tick:event.tick,duration_ticks:event.duration_ticks,onset_seconds:start,duration_seconds:end-start,tempo_bpm:Number(context.tempo_bpm),time_signature:clone(context.time_signature),key:clone(context.key),a4_hz:Number(context.tuning.a4_hz)});
      }
    }
    rows.sort((a,b)=>a.onset_seconds-b.onset_seconds||a.track_id.localeCompare(b.track_id)||a.event.id.localeCompare(b.event.id));
    return rows;
  }
  function migrateV1ToV2(score, registryDoc, noteToMidi) {
    const tempo=Number(score.tempo_bpm??DEFAULT_TEMPO_BPM);
    const maxEnd=Math.max(4,...score.events.map(event=>Number(event.onset)+Number(event.duration)));
    const lengthTicks=Math.max(TICKS_PER_QUARTER,Math.ceil(maxEnd*TICKS_PER_QUARTER));
    const defaults=factoryDefaults(); defaults.tempo_bpm=tempo;
    const sourceMap=new Map(registryDoc.sources.map(source=>[source.id,source]));
    const grouped=new Map();
    for (const event of score.events) {
      if (!grouped.has(event.source)) grouped.set(event.source,[]);
      grouped.get(event.source).push(event);
    }
    const tracks=[]; let index=1;
    for (const [sourceId,events] of grouped) {
      const objects=events.map(event=>{
        const obj={id:event.id,type:event.pitch?"note":"event",gesture:event.gesture,tick:Math.round(Number(event.onset)*TICKS_PER_QUARTER),duration_ticks:Math.max(1,Math.round(Number(event.duration)*TICKS_PER_QUARTER)),dynamics:event.dynamics??.75,articulation:event.articulation??"normal"};
        if (event.pitch) obj.pitch=clone(event.pitch); if (event.pitch_curve) obj.pitch_curve=clone(event.pitch_curve); return obj;
      });
      const glyph=sourceMap.get(sourceId)?.glyph??sourceId;
      tracks.push({id:`track-${index}`,name:`${glyph} ${sourceId}`,context:{},sections:[{id:`track-${index}-section-1`,start_tick:0,end_tick:lengthTicks,source:sourceId,context:{},objects}]});
      index++;
    }
    const result={format:"esn/2",title:score.title,length_ticks:lengthTicks,defaults,tracks};
    if (score.metadata) result.metadata=clone(score.metadata);
    validateScoreV2(result,registryDoc,noteToMidi);
    return result;
  }
  function documentRows(score, registryDoc, noteToMidi) {
    if (score.format==="esn/2") return flattenScore(score,registryDoc,noteToMidi);
    const tempo=Number(score.tempo_bpm??120), beatSeconds=60/tempo;
    return score.events.map(event=>({track_id:event.source,section_id:event.source,object_id:event.id,object_type:"event",event:clone(event),tick:Math.round(Number(event.onset)*TICKS_PER_QUARTER),duration_ticks:Math.max(1,Math.round(Number(event.duration)*TICKS_PER_QUARTER)),onset_seconds:Number(event.onset)*beatSeconds,duration_seconds:Number(event.duration)*beatSeconds,tempo_bpm:tempo,time_signature:{numerator:4,denominator:4},key:{tonic:"C",scale:"chromatic"},a4_hz:440}));
  }
  const api={TICKS_PER_QUARTER,DEFAULT_TEMPO_BPM,DEFAULT_A4_HZ,factoryDefaults,resolveContext,expandChordPitches,validateScoreV2,splitSection,assignSectionSource,explodeChord,flattenScore,migrateV1ToV2,documentRows,trackTimeAtTick};
  root.EsnScoreDomain=api;
  if (typeof module!=="undefined"&&module.exports) module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:window);
