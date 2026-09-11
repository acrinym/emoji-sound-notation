from __future__ import annotations

import copy
import math
import re
from typing import Any

from .model import ARTICULATIONS, ValidationError, note_to_midi, validate_score

TICKS_PER_QUARTER = 9600
DEFAULT_TEMPO_BPM = 96
DEFAULT_A4_HZ = 432.0
DEFAULT_TIME_SIGNATURE = {"numerator": 4, "denominator": 4}
DEFAULT_KEY = {"tonic": "C", "scale": "major"}

SCORE_KEYS = {"format", "title", "length_ticks", "defaults", "metadata", "tracks"}
DEFAULT_KEYS = {"tempo_bpm", "time_signature", "key", "tuning"}
TRACK_KEYS = {"id", "name", "context", "sections"}
SECTION_KEYS = {"id", "start_tick", "end_tick", "source", "context", "objects"}
CONTEXT_KEYS = DEFAULT_KEYS
COMMON_OBJECT_KEYS = {"id", "type", "gesture", "tick", "duration_ticks", "dynamics", "articulation"}
NOTE_EVENT_KEYS = COMMON_OBJECT_KEYS | {"pitch", "pitch_curve"}
CHORD_KEYS = COMMON_OBJECT_KEYS | {"root", "quality", "inversion", "voicing", "arpeggiation"}
TIME_SIGNATURE_KEYS = {"numerator", "denominator"}
KEY_KEYS = {"tonic", "scale"}
TUNING_KEYS = {"a4_hz"}

SCALES = {"major", "minor", "major_pentatonic", "minor_pentatonic", "chromatic"}
CHORD_INTERVALS = {
    "major": [0, 4, 7], "minor": [0, 3, 7], "diminished": [0, 3, 6],
    "augmented": [0, 4, 8], "sus2": [0, 2, 7], "sus4": [0, 5, 7],
    "dominant7": [0, 4, 7, 10], "major7": [0, 4, 7, 11], "minor7": [0, 3, 7, 10],
    "major_pentatonic": [0, 2, 4, 7, 9], "minor_pentatonic": [0, 3, 5, 7, 10],
}
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
TONIC_RE = re.compile(r"^[A-G](?:#|b)?$")


def factory_defaults() -> dict[str, Any]:
    return {
        "tempo_bpm": DEFAULT_TEMPO_BPM,
        "time_signature": dict(DEFAULT_TIME_SIGNATURE),
        "key": dict(DEFAULT_KEY),
        "tuning": {"a4_hz": DEFAULT_A4_HZ},
    }


def _number(value: Any, label: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError(f"{label} must be finite")
    if minimum is not None and result < minimum:
        raise ValidationError(f"{label} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise ValidationError(f"{label} must be <= {maximum}")
    return result


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{label} must be >= {minimum}")
    return value


def _require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def _validate_time_signature(value: Any, label: str) -> None:
    if not isinstance(value, dict) or set(value) != TIME_SIGNATURE_KEYS:
        raise ValidationError(f"{label} must contain numerator and denominator")
    _integer(value["numerator"], f"{label}.numerator", minimum=1)
    denominator = _integer(value["denominator"], f"{label}.denominator", minimum=1)
    if denominator not in {1, 2, 4, 8, 16, 32, 64}:
        raise ValidationError(f"{label}.denominator must be a power-of-two musical denominator")


def _validate_key(value: Any, label: str) -> None:
    if not isinstance(value, dict) or set(value) != KEY_KEYS:
        raise ValidationError(f"{label} must contain tonic and scale")
    if not isinstance(value["tonic"], str) or not TONIC_RE.fullmatch(value["tonic"]):
        raise ValidationError(f"{label}.tonic must be a pitch class such as C, F#, or Bb")
    if value["scale"] not in SCALES:
        raise ValidationError(f"{label}.scale must be one of {sorted(SCALES)}")


def _validate_tuning(value: Any, label: str) -> None:
    if not isinstance(value, dict) or set(value) != TUNING_KEYS:
        raise ValidationError(f"{label} must contain only a4_hz")
    _number(value["a4_hz"], f"{label}.a4_hz", minimum=1, maximum=20000)


def _validate_context(value: Any, label: str, *, complete: bool = False) -> None:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    extra = set(value) - CONTEXT_KEYS
    if extra:
        raise ValidationError(f"{label} contains unknown fields: {sorted(extra)}")
    if complete and set(value) != DEFAULT_KEYS:
        raise ValidationError(f"{label} must contain tempo_bpm, time_signature, key, and tuning")
    if "tempo_bpm" in value:
        _number(value["tempo_bpm"], f"{label}.tempo_bpm", minimum=1)
    if "time_signature" in value:
        _validate_time_signature(value["time_signature"], f"{label}.time_signature")
    if "key" in value:
        _validate_key(value["key"], f"{label}.key")
    if "tuning" in value:
        _validate_tuning(value["tuning"], f"{label}.tuning")


def resolve_context(defaults: dict[str, Any], track_context: dict[str, Any], section_context: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(defaults)
    for layer in (track_context, section_context):
        for key, value in layer.items():
            result[key] = copy.deepcopy(value)
    return result


def _midi_to_note(midi: int) -> str:
    if not 0 <= midi <= 127:
        raise ValidationError("expanded chord note is outside MIDI range")
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def expand_chord_pitches(chord: dict[str, Any]) -> list[str]:
    root = chord.get("root")
    quality = chord.get("quality")
    inversion = chord.get("inversion", 0)
    if not isinstance(root, str):
        raise ValidationError("chord root must be a note name")
    root_midi = note_to_midi(root)
    if quality not in CHORD_INTERVALS:
        raise ValidationError(f"unknown chord quality: {quality!r}")
    intervals = list(CHORD_INTERVALS[quality])
    if isinstance(inversion, bool) or not isinstance(inversion, int) or not 0 <= inversion < len(intervals):
        raise ValidationError("chord inversion must select one of the chord voices")
    midis = [root_midi + interval for interval in intervals]
    for index in range(inversion):
        midis[index] += 12
    midis.sort()
    if chord.get("voicing", "close") == "open" and len(midis) >= 3:
        midis[1] += 12
        midis.sort()
    return [_midi_to_note(midi) for midi in midis]


def _validate_pitch_curve(curve: Any, label: str) -> None:
    if curve is None:
        return
    if not isinstance(curve, list) or not curve:
        raise ValidationError(f"{label} must be a non-empty array")
    previous = -1.0
    for index, point in enumerate(curve):
        if not isinstance(point, dict) or set(point) != {"at", "pitch"}:
            raise ValidationError(f"{label}[{index}] must contain only at and pitch")
        at = _number(point["at"], f"{label}[{index}].at", minimum=0, maximum=1)
        if at <= previous:
            raise ValidationError(f"{label} positions must strictly increase")
        previous = at
        if not isinstance(point["pitch"], dict):
            raise ValidationError(f"{label}[{index}].pitch must be an object")


def _validate_object(obj: Any, source: dict[str, Any], section: dict[str, Any], label: str) -> None:
    if not isinstance(obj, dict):
        raise ValidationError(f"{label} must be an object")
    kind = obj.get("type")
    allowed = CHORD_KEYS if kind == "chord" else NOTE_EVENT_KEYS
    extra = set(obj) - allowed
    if extra:
        raise ValidationError(f"{label} contains unknown fields: {sorted(extra)}")
    _require_id(obj.get("id"), f"{label}.id")
    if kind not in {"note", "event", "chord"}:
        raise ValidationError(f"{label}.type must be note, event, or chord")
    gesture = obj.get("gesture")
    if gesture not in source["gestures"]:
        raise ValidationError(f"{label}.gesture {gesture!r} is not valid for {source['id']}")
    tick = _integer(obj.get("tick"), f"{label}.tick", minimum=0)
    duration = _integer(obj.get("duration_ticks"), f"{label}.duration_ticks", minimum=1)
    if tick < section["start_tick"] or tick + duration > section["end_tick"]:
        raise ValidationError(f"{label} must fit within its section")
    dynamics = _number(obj.get("dynamics", 0.75), f"{label}.dynamics", minimum=0, maximum=1)
    articulation = obj.get("articulation", "normal")
    if articulation not in ARTICULATIONS:
        raise ValidationError(f"{label}.articulation is not recognized: {articulation!r}")
    policy = source.get("pitch_policy", "optional")
    if kind == "chord":
        if policy == "forbidden":
            raise ValidationError(f"{label} cannot be a chord because {source['id']} forbids pitch")
        pitches = expand_chord_pitches(obj)
        if obj.get("voicing", "close") not in {"close", "open"}:
            raise ValidationError(f"{label}.voicing must be close or open")
        arp = obj.get("arpeggiation")
        if arp is not None:
            if not isinstance(arp, dict) or set(arp) != {"direction", "step_ticks"}:
                raise ValidationError(f"{label}.arpeggiation must contain direction and step_ticks")
            if arp["direction"] not in {"up", "down"}:
                raise ValidationError(f"{label}.arpeggiation.direction must be up or down")
            step_ticks = _integer(arp["step_ticks"], f"{label}.arpeggiation.step_ticks", minimum=0)
            realized_end = tick + duration + (len(pitches) - 1) * step_ticks
            if realized_end > section["end_tick"]:
                raise ValidationError(f"{label} arpeggiation must fit every realized voice within its section")
        return

    pitch = obj.get("pitch")
    if kind == "note" and pitch is None:
        raise ValidationError(f"{label}.pitch is required for note objects")
    if policy == "required" and pitch is None:
        raise ValidationError(f"{label}.pitch is required for {source['id']}")
    if policy == "forbidden" and pitch is not None:
        raise ValidationError(f"{label}.pitch is forbidden for {source['id']}")
    if pitch is not None:
        if not isinstance(pitch, dict):
            raise ValidationError(f"{label}.pitch must be an object")
        from .model import pitch_to_midi
        pitch_to_midi(pitch)
    curve = obj.get("pitch_curve")
    if curve is not None and pitch is None:
        raise ValidationError(f"{label}.pitch_curve requires a starting pitch")
    _validate_pitch_curve(curve, f"{label}.pitch_curve")


def validate_score_v2(data: dict[str, Any], registry: dict[str, dict[str, Any]]) -> None:
    if not isinstance(data, dict):
        raise ValidationError("score root must be an object")
    extra = set(data) - SCORE_KEYS
    if extra:
        raise ValidationError(f"score contains unknown fields: {sorted(extra)}")
    if data.get("format") != "esn/2":
        raise ValidationError("score format must be 'esn/2'")
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        raise ValidationError("score title must be a non-empty string")
    length_ticks = _integer(data.get("length_ticks"), "length_ticks", minimum=1)
    _validate_context(data.get("defaults"), "defaults", complete=True)
    if "metadata" in data and not isinstance(data["metadata"], dict):
        raise ValidationError("metadata must be an object")
    tracks = data.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValidationError("tracks must be a non-empty array")

    ids: set[str] = set()
    for track_index, track in enumerate(tracks):
        _validate_track(track, registry, length_ticks, ids, f"tracks[{track_index}]")


def _validate_track(track: Any, registry: dict[str, dict[str, Any]], length_ticks: int,
                    ids: set[str], label: str) -> None:
    if not isinstance(track, dict):
        raise ValidationError(f"{label} must be an object")
    extra = set(track) - TRACK_KEYS
    if extra:
        raise ValidationError(f"{label} contains unknown fields: {sorted(extra)}")
    track_id = _require_id(track.get("id"), f"{label}.id")
    if track_id in ids:
        raise ValidationError(f"duplicate id: {track_id}")
    ids.add(track_id)
    if not isinstance(track.get("name"), str) or not track["name"].strip():
        raise ValidationError(f"{label}.name must be a non-empty string")
    _validate_context(track.get("context", {}), f"{label}.context")
    sections = track.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValidationError(f"{label}.sections must be a non-empty array")
    previous_end = -1
    for section_index, section in enumerate(sections):
        section_label = f"{label}.sections[{section_index}]"
        if not isinstance(section, dict):
            raise ValidationError(f"{section_label} must be an object")
        extra = set(section) - SECTION_KEYS
        if extra:
            raise ValidationError(f"{section_label} contains unknown fields: {sorted(extra)}")
        section_id = _require_id(section.get("id"), f"{section_label}.id")
        if section_id in ids:
            raise ValidationError(f"duplicate id: {section_id}")
        ids.add(section_id)
        start = _integer(section.get("start_tick"), f"{section_label}.start_tick", minimum=0)
        end = _integer(section.get("end_tick"), f"{section_label}.end_tick", minimum=1)
        if not start < end <= length_ticks:
            raise ValidationError(f"{section_label} must fit within length_ticks")
        if previous_end > start:
            raise ValidationError(f"{section_label} overlaps the previous section")
        previous_end = end
        source_id = section.get("source")
        objects = section.get("objects")
        if not isinstance(objects, list):
            raise ValidationError(f"{section_label}.objects must be an array")
        if source_id is None:
            if objects:
                raise ValidationError(f"{section_label}.source is required when the section contains objects")
            source = None
        elif source_id not in registry:
            raise ValidationError(f"{section_label}.source is not registered: {source_id!r}")
        else:
            source = registry[source_id]
        _validate_context(section.get("context", {}), f"{section_label}.context")
        for object_index, obj in enumerate(objects):
            object_label = f"{section_label}.objects[{object_index}]"
            object_id = obj.get("id") if isinstance(obj, dict) else None
            if isinstance(object_id, str) and object_id in ids:
                raise ValidationError(f"duplicate id: {object_id}")
            _validate_object(obj, source, section, object_label)
            ids.add(object_id)


def _track_by_id(score: dict[str, Any], track_id: str) -> dict[str, Any]:
    for track in score["tracks"]:
        if track["id"] == track_id:
            return track
    raise ValidationError(f"unknown track id: {track_id}")


def split_section(score: dict[str, Any], track_id: str, section_id: str, split_tick: int) -> dict[str, Any]:
    result = copy.deepcopy(score)
    track = _track_by_id(result, track_id)
    for index, section in enumerate(track["sections"]):
        if section["id"] != section_id:
            continue
        if not section["start_tick"] < split_tick < section["end_tick"]:
            raise ValidationError("split_tick must be inside the section")
        if any(obj["tick"] >= split_tick or obj["tick"] + obj["duration_ticks"] > split_tick
               for obj in section["objects"]):
            raise ValidationError("split would move or cut existing objects; reposition them first")
        used_section_ids = {item["id"] for candidate_track in result["tracks"] for item in candidate_track["sections"]}
        split_base = f"{section_id}-split"
        split_id = split_base
        suffix = 2
        while split_id in used_section_ids:
            split_id = f"{split_base}-{suffix}"
            suffix += 1
        right = {
            "id": split_id,
            "start_tick": split_tick,
            "end_tick": section["end_tick"],
            "source": None,
            "context": copy.deepcopy(section.get("context", {})),
            "objects": [],
        }
        section["end_tick"] = split_tick
        track["sections"][index:index + 1] = [section, right]
        return result
    raise ValidationError(f"unknown section id: {section_id}")


def assign_section_source(score: dict[str, Any], track_id: str, section_id: str, source_id: str,
                          registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if source_id not in registry:
        raise ValidationError(f"unknown source: {source_id}")
    result = copy.deepcopy(score)
    track = _track_by_id(result, track_id)
    for section in track["sections"]:
        if section["id"] == section_id:
            if section["objects"]:
                raise ValidationError("cannot change a populated section source without moving its objects")
            section["source"] = source_id
            return result
    raise ValidationError(f"unknown section id: {section_id}")


def explode_chord(score: dict[str, Any], chord_id: str, registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(score)
    for track in result["tracks"]:
        for section in track["sections"]:
            for index, obj in enumerate(section["objects"]):
                if obj.get("id") != chord_id:
                    continue
                if obj.get("type") != "chord":
                    raise ValidationError(f"object {chord_id} is not a chord")
                notes = []
                pitches = expand_chord_pitches(obj)
                for voice, pitch in enumerate(pitches, start=1):
                    note = {
                        "id": f"{chord_id}-v{voice}",
                        "type": "note",
                        "gesture": obj["gesture"],
                        "tick": obj["tick"],
                        "duration_ticks": obj["duration_ticks"],
                        "pitch": {"note": pitch},
                        "dynamics": obj.get("dynamics", 0.75),
                        "articulation": obj.get("articulation", "normal"),
                    }
                    arp = obj.get("arpeggiation")
                    if arp:
                        order = voice - 1 if arp["direction"] == "up" else len(pitches) - voice
                        note["tick"] += order * arp["step_ticks"]
                    notes.append(note)
                section["objects"][index:index + 1] = notes
                validate_score_v2(result, registry)
                return result
    raise ValidationError(f"unknown chord id: {chord_id}")


def _seconds_for_ticks(ticks: int, tempo_bpm: float) -> float:
    return (ticks / TICKS_PER_QUARTER) * (60.0 / tempo_bpm)


def _context_at_tick(score: dict[str, Any], track: dict[str, Any], tick: int) -> dict[str, Any]:
    base = resolve_context(score["defaults"], track.get("context", {}), {})
    for section in track["sections"]:
        if section["start_tick"] <= tick < section["end_tick"]:
            return resolve_context(score["defaults"], track.get("context", {}), section.get("context", {}))
    return base


def _track_time_at_tick(score: dict[str, Any], track: dict[str, Any], tick: int) -> float:
    if tick <= 0:
        return 0.0
    tick = min(tick, score["length_ticks"])
    boundaries = {0, tick}
    for section in track["sections"]:
        if 0 < section["start_tick"] < tick:
            boundaries.add(section["start_tick"])
        if 0 < section["end_tick"] < tick:
            boundaries.add(section["end_tick"])
    ordered = sorted(boundaries)
    seconds = 0.0
    for left, right in zip(ordered, ordered[1:]):
        context = _context_at_tick(score, track, left)
        seconds += _seconds_for_ticks(right - left, float(context["tempo_bpm"]))
    return seconds


def _object_events(obj: dict[str, Any], source_id: str) -> list[dict[str, Any]]:
    if obj["type"] != "chord":
        event = {
            "id": obj["id"], "source": source_id, "gesture": obj["gesture"],
            "tick": obj["tick"], "duration_ticks": obj["duration_ticks"],
            "dynamics": obj.get("dynamics", 0.75),
            "articulation": obj.get("articulation", "normal"),
        }
        if "pitch" in obj:
            event["pitch"] = copy.deepcopy(obj["pitch"])
        if "pitch_curve" in obj:
            event["pitch_curve"] = copy.deepcopy(obj["pitch_curve"])
        return [event]

    pitches = expand_chord_pitches(obj)
    arp = obj.get("arpeggiation")
    events = []
    for index, pitch in enumerate(pitches):
        order = index if not arp or arp["direction"] == "up" else len(pitches) - index - 1
        offset = 0 if not arp else order * arp["step_ticks"]
        events.append({
            "id": f"{obj['id']}-v{index + 1}", "source": source_id,
            "gesture": obj["gesture"], "tick": obj["tick"] + offset,
            "duration_ticks": obj["duration_ticks"], "pitch": {"note": pitch},
            "dynamics": obj.get("dynamics", 0.75),
            "articulation": obj.get("articulation", "normal"),
            "chord_id": obj["id"],
        })
    return events


def flatten_score(score: dict[str, Any], registry: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    validate_score_v2(score, registry)
    rows: list[dict[str, Any]] = []
    for track in score["tracks"]:
        for section in track["sections"]:
            context = resolve_context(score["defaults"], track.get("context", {}), section.get("context", {}))
            for obj in section["objects"]:
                for event in _object_events(obj, section["source"]):
                    start_s = _track_time_at_tick(score, track, event["tick"])
                    end_s = _track_time_at_tick(score, track, event["tick"] + event["duration_ticks"])
                    legacy_event = {
                        key: copy.deepcopy(value)
                        for key, value in event.items()
                        if key not in {"tick", "duration_ticks", "chord_id"}
                    }
                    legacy_event["onset"] = event["tick"] / TICKS_PER_QUARTER
                    legacy_event["duration"] = event["duration_ticks"] / TICKS_PER_QUARTER
                    rows.append({
                        "track_id": track["id"], "section_id": section["id"],
                        "object_id": obj["id"], "object_type": obj["type"],
                        "event": legacy_event,
                        "tick": event["tick"], "duration_ticks": event["duration_ticks"],
                        "onset_seconds": start_s, "duration_seconds": end_s - start_s,
                        "tempo_bpm": float(context["tempo_bpm"]),
                        "time_signature": copy.deepcopy(context["time_signature"]),
                        "key": copy.deepcopy(context["key"]),
                        "a4_hz": float(context["tuning"]["a4_hz"]),
                    })
    rows.sort(key=lambda row: (row["onset_seconds"], row["track_id"], row["event"]["id"]))
    return rows


def migrate_v1_to_v2(score: dict[str, Any], registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    validate_score(score, registry)
    tempo = float(score.get("tempo_bpm", DEFAULT_TEMPO_BPM))
    max_end = max((float(event["onset"]) + float(event["duration"]) for event in score["events"]), default=4.0)
    length_ticks = max(TICKS_PER_QUARTER, int(math.ceil(max_end * TICKS_PER_QUARTER)))
    defaults = factory_defaults()
    defaults["tempo_bpm"] = tempo
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in score["events"]:
        grouped.setdefault(event["source"], []).append(event)

    tracks = []
    for index, (source_id, events) in enumerate(grouped.items(), start=1):
        objects = []
        for event in events:
            obj = {
                "id": event["id"], "type": "note" if "pitch" in event else "event",
                "gesture": event["gesture"],
                "tick": int(round(float(event["onset"]) * TICKS_PER_QUARTER)),
                "duration_ticks": max(1, int(round(float(event["duration"]) * TICKS_PER_QUARTER))),
                "dynamics": event.get("dynamics", 0.75),
                "articulation": event.get("articulation", "normal"),
            }
            if "pitch" in event:
                obj["pitch"] = copy.deepcopy(event["pitch"])
            if "pitch_curve" in event:
                obj["pitch_curve"] = copy.deepcopy(event["pitch_curve"])
            objects.append(obj)
        tracks.append({
            "id": f"track-{index}", "name": registry[source_id].get("glyph", source_id) + " " + source_id,
            "context": {},
            "sections": [{
                "id": f"track-{index}-section-1", "start_tick": 0, "end_tick": length_ticks,
                "source": source_id, "context": {}, "objects": objects,
            }],
        })
    result = {
        "format": "esn/2", "title": score["title"], "length_ticks": length_ticks,
        "defaults": defaults, "tracks": tracks,
    }
    if "metadata" in score:
        result["metadata"] = copy.deepcopy(score["metadata"])
    return result


def validate_document(score: dict[str, Any], registry: dict[str, dict[str, Any]]) -> None:
    if score.get("format") == "esn/2":
        validate_score_v2(score, registry)
    else:
        validate_score(score, registry)


def pitch_to_midi_with_tuning(pitch: dict[str, Any], a4_hz: float) -> float:
    if set(pitch) == {"note"} and isinstance(pitch["note"], str):
        return float(note_to_midi(pitch["note"]))
    if set(pitch) == {"hz"} and not isinstance(pitch["hz"], bool) and isinstance(pitch["hz"], (int, float)):
        hz = _number(pitch["hz"], "pitch.hz", minimum=0.000001)
        return 69.0 + 12.0 * math.log2(hz / a4_hz)
    raise ValidationError("pitch must contain exactly one of string 'note' or numeric 'hz'")


def midi_to_hz_with_tuning(midi: float, a4_hz: float) -> float:
    return a4_hz * (2.0 ** ((midi - 69.0) / 12.0))


def document_rows(score: dict[str, Any], registry: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if score.get("format") == "esn/2":
        return flatten_score(score, registry)
    validate_score(score, registry)
    tempo = float(score.get("tempo_bpm", 120))
    beat_seconds = 60.0 / tempo
    rows = []
    for event in score["events"]:
        rows.append({
            "track_id": event["source"], "section_id": event["source"],
            "object_id": event["id"], "object_type": "event",
            "event": copy.deepcopy(event),
            "tick": int(round(float(event["onset"]) * TICKS_PER_QUARTER)),
            "duration_ticks": max(1, int(round(float(event["duration"]) * TICKS_PER_QUARTER))),
            "onset_seconds": float(event["onset"]) * beat_seconds,
            "duration_seconds": float(event["duration"]) * beat_seconds,
            "tempo_bpm": tempo, "time_signature": {"numerator": 4, "denominator": 4},
            "key": {"tonic": "C", "scale": "chromatic"}, "a4_hz": 440.0,
        })
    return rows
