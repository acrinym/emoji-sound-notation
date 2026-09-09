from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PITCH_POLICIES = {"required", "optional", "forbidden"}
ARTICULATIONS = {"normal", "staccato", "tenuto", "accent", "legato"}


class ValidationError(ValueError):
    """Raised when an ESN document violates the semantic contract."""


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValidationError("document root must be an object")
    return value


def note_to_midi(note: str) -> int:
    match = NOTE_RE.fullmatch(note)
    if not match:
        raise ValidationError(f"invalid note name: {note!r}")
    name, accidental, octave_text = match.groups()
    semitone = NOTE_OFFSETS[name.upper()]
    if accidental == "#":
        semitone += 1
    elif accidental == "b":
        semitone -= 1
    midi = (int(octave_text) + 1) * 12 + semitone
    if not 0 <= midi <= 127:
        raise ValidationError(f"note outside MIDI range: {note!r}")
    return midi


def hz_to_midi(hz: float) -> float:
    if not math.isfinite(hz) or hz <= 0:
        raise ValidationError("frequency must be a finite positive number")
    return 69.0 + 12.0 * math.log2(hz / 440.0)


def pitch_to_midi(pitch: dict[str, Any]) -> float:
    if set(pitch) == {"note"} and isinstance(pitch["note"], str):
        return float(note_to_midi(pitch["note"]))
    if set(pitch) == {"hz"} and isinstance(pitch["hz"], (int, float)):
        return hz_to_midi(float(pitch["hz"]))
    raise ValidationError("pitch must contain exactly one of string 'note' or numeric 'hz'")


def load_registry(path: str | Path) -> dict[str, dict[str, Any]]:
    data = load_json(path)
    if data.get("format") != "esn-registry/1":
        raise ValidationError("registry format must be 'esn-registry/1'")
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValidationError("registry sources must be a non-empty array")
    sources: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(raw_sources):
        where = f"registry.sources[{index}]"
        if not isinstance(source, dict):
            raise ValidationError(f"{where} must be an object")
        source_id = source.get("id")
        glyph = source.get("glyph")
        gestures = source.get("gestures")
        policy = source.get("pitch_policy", "optional")
        if not isinstance(source_id, str) or not source_id:
            raise ValidationError(f"{where}.id must be a non-empty string")
        if source_id in sources:
            raise ValidationError(f"duplicate registry source id: {source_id}")
        if not isinstance(glyph, str) or not glyph:
            raise ValidationError(f"{where}.glyph must be a non-empty string")
        if not isinstance(gestures, list) or not gestures or not all(isinstance(x, str) and x for x in gestures):
            raise ValidationError(f"{where}.gestures must be a non-empty string array")
        if len(set(gestures)) != len(gestures):
            raise ValidationError(f"{where}.gestures contains duplicates")
        if policy not in PITCH_POLICIES:
            raise ValidationError(f"{where}.pitch_policy must be required, optional, or forbidden")
        sources[source_id] = source
    return sources


def _number(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise ValidationError(f"{label} must be finite and >= {minimum}")
    return result
def validate_score(data: dict[str, Any], registry: dict[str, dict[str, Any]]) -> None:
    if data.get("format") != "esn/1":
        raise ValidationError("score format must be 'esn/1'")
    if not isinstance(data.get("title"), str) or not data["title"]:
        raise ValidationError("score title must be a non-empty string")
    _number(data.get("tempo_bpm", 120), "tempo_bpm", minimum=1)
    events = data.get("events")
    if not isinstance(events, list):
        raise ValidationError("events must be an array")

    seen_ids: set[str] = set()
    for index, event in enumerate(events):
        where = f"events[{index}]"
        if not isinstance(event, dict):
            raise ValidationError(f"{where} must be an object")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise ValidationError(f"{where}.id must be a non-empty string")
        if event_id in seen_ids:
            raise ValidationError(f"duplicate event id: {event_id}")
        seen_ids.add(event_id)
        source_id = event.get("source")
        if source_id not in registry:
            raise ValidationError(f"{where}.source is not registered: {source_id!r}")
        source = registry[source_id]
        gesture = event.get("gesture")
        if gesture not in source["gestures"]:
            raise ValidationError(f"{where}.gesture {gesture!r} is not valid for {source_id}")
        _number(event.get("onset"), f"{where}.onset", minimum=0)
        _number(event.get("duration"), f"{where}.duration", minimum=0.000001)
        dynamics = _number(event.get("dynamics", 0.75), f"{where}.dynamics", minimum=0)
        if dynamics > 1:
            raise ValidationError(f"{where}.dynamics must be <= 1")
        articulation = event.get("articulation", "normal")
        if articulation not in ARTICULATIONS:
            raise ValidationError(f"{where}.articulation is not recognized: {articulation!r}")

        pitch = event.get("pitch")
        policy = source.get("pitch_policy", "optional")
        if policy == "required" and pitch is None:
            raise ValidationError(f"{where}.pitch is required for {source_id}")
        if policy == "forbidden" and pitch is not None:
            raise ValidationError(f"{where}.pitch is forbidden for {source_id}")
        if pitch is not None:
            if not isinstance(pitch, dict):
                raise ValidationError(f"{where}.pitch must be an object")
            pitch_to_midi(pitch)

        curve = event.get("pitch_curve")
        if curve is not None:
            if pitch is None:
                raise ValidationError(f"{where}.pitch_curve requires a starting pitch")
            if not isinstance(curve, list) or not curve:
                raise ValidationError(f"{where}.pitch_curve must be a non-empty array")
            previous = -1.0
            for point_index, point in enumerate(curve):
                if not isinstance(point, dict) or set(point) != {"at", "pitch"}:
                    raise ValidationError(f"{where}.pitch_curve[{point_index}] must contain only at and pitch")
                at = _number(point["at"], f"{where}.pitch_curve[{point_index}].at", minimum=0)
                if at > 1 or at <= previous:
                    raise ValidationError(f"{where}.pitch_curve positions must strictly increase within 0..1")
                previous = at
                if not isinstance(point["pitch"], dict):
                    raise ValidationError(f"{where}.pitch_curve[{point_index}].pitch must be an object")
                pitch_to_midi(point["pitch"])


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
