from __future__ import annotations

import csv
import io
import json
import math
import struct
from pathlib import Path
from typing import Any

from .model import ValidationError, load_json, pitch_to_midi, validate_score

PROFILE_KEYS = {"format", "name", "ticks_per_quarter", "cue_prefix", "midi_sources"}
MAPPING_KEYS = {"source", "mode", "channel", "program", "note"}
MAPPING_MODES = {"pitched", "fixed"}


def _int(value: Any, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValidationError(f"{label} must be an integer from {low} through {high}")
    return value


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def load_interchange_profile(path: str | Path, registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    data = load_json(path)
    extra = set(data) - PROFILE_KEYS
    if extra:
        raise ValidationError(f"interchange profile contains unknown fields: {sorted(extra)}")
    if data.get("format") != "esn-interchange/1":
        raise ValidationError("interchange profile format must be 'esn-interchange/1'")
    if not isinstance(data.get("name"), str) or not data["name"]:
        raise ValidationError("interchange profile name must be non-empty")
    tpq = _int(data.get("ticks_per_quarter"), "ticks_per_quarter", 24, 32767)
    prefix = data.get("cue_prefix")
    if not isinstance(prefix, str) or not prefix or len(prefix) > 32:
        raise ValidationError("cue_prefix must be a non-empty string of at most 32 characters")
    try:
        prefix.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValidationError("cue_prefix must be ASCII") from exc
    raw = data.get("midi_sources")
    if not isinstance(raw, list):
        raise ValidationError("midi_sources must be an array")

    mappings: dict[str, dict[str, Any]] = {}
    channel_programs: dict[int, int | None] = {}
    for index, mapping in enumerate(raw):
        where = f"midi_sources[{index}]"
        if not isinstance(mapping, dict):
            raise ValidationError(f"{where} must be an object")
        extra = set(mapping) - MAPPING_KEYS
        if extra:
            raise ValidationError(f"{where} contains unknown fields: {sorted(extra)}")
        source = mapping.get("source")
        if source not in registry:
            raise ValidationError(f"{where}.source is not registered: {source!r}")
        if source in mappings:
            raise ValidationError(f"duplicate MIDI mapping for {source}")
        mode = mapping.get("mode")
        if mode not in MAPPING_MODES:
            raise ValidationError(f"{where}.mode must be one of {sorted(MAPPING_MODES)}")
        channel = _int(mapping.get("channel"), f"{where}.channel", 0, 15)
        program = None
        if "program" in mapping:
            program = _int(mapping["program"], f"{where}.program", 0, 127)
        if channel in channel_programs and channel_programs[channel] != program:
            raise ValidationError(f"{where}.channel conflicts with another mapping using a different program")
        channel_programs[channel] = program
        if mode == "fixed":
            if "note" not in mapping:
                raise ValidationError(f"{where}.note is required for fixed mode")
            _int(mapping["note"], f"{where}.note", 0, 127)
        elif "note" in mapping:
            raise ValidationError(f"{where}.note is only valid for fixed mode")
        mappings[source] = dict(mapping)

    return {
        "name": data["name"],
        "ticks_per_quarter": tpq,
        "cue_prefix": prefix,
        "mappings": mappings,
    }


def _vlq(value: int) -> bytes:
    if value < 0 or value > 0x0FFFFFFF:
        raise ValidationError("MIDI variable-length quantity is out of range")
    buffer = value & 0x7F
    out = bytearray([buffer])
    while value >> 7:
        value >>= 7
        buffer = (value & 0x7F) | 0x80
        out.insert(0, buffer)
    return bytes(out)


def _meta(kind: int, payload: bytes) -> bytes:
    return bytes([0xFF, kind]) + _vlq(len(payload)) + payload

def _track(events: list[tuple[int, int, bytes]]) -> bytes:
    ordered = sorted(events, key=lambda item: (item[0], item[1], item[2]))
    payload = bytearray()
    previous = 0
    for tick, _priority, message in ordered:
        if tick < previous:
            raise ValidationError("MIDI track events are not monotonic")
        payload.extend(_vlq(tick - previous))
        payload.extend(message)
        previous = tick
    payload.extend(_vlq(0))
    payload.extend(_meta(0x2F, b""))
    return b"MTrk" + struct.pack(">I", len(payload)) + bytes(payload)


def _ascii_text(text: str) -> bytes:
    return text.encode("ascii", "backslashreplace")


def _event_cue(prefix: str, event: dict[str, Any]) -> bytes:
    body = json.dumps(event, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return _ascii_text(prefix + body)


def _event_mapping(event: dict[str, Any], profile: dict[str, Any]) -> tuple[dict[str, Any] | None, int | None, list[str]]:
    mapping = profile["mappings"].get(event["source"])
    losses: list[str] = []
    if mapping is None:
        return None, None, ["cue_only"]
    if mapping["mode"] == "pitched":
        if "pitch" not in event:
            return mapping, None, ["pitch_required"]
        note = _round_half_up(pitch_to_midi(event["pitch"]))
    else:
        note = int(mapping["note"])
    if event.get("pitch_curve"):
        losses.append("pitch_curve_flattened")
    return mapping, max(0, min(127, note)), losses

def _midi_plan(score: dict[str, Any], profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    reserved = {int(mapping["channel"]) for mapping in profile["mappings"].values()}
    auxiliaries = [channel for channel in range(16) if channel not in reserved and channel != 9]
    auxiliary_programs: dict[int, int] = {}
    active_until: dict[tuple[int, int], int] = {}
    entries = []
    tpq = profile["ticks_per_quarter"]
    for index, event in enumerate(score["events"]):
        mapping, note, losses = _event_mapping(event, profile)
        onset_tick = _round_half_up(float(event["onset"]) * tpq)
        duration_tick = max(1, _round_half_up(float(event["duration"]) * tpq))
        entries.append((onset_tick, index, event, mapping, note, list(losses), duration_tick))
    plan: dict[str, dict[str, Any]] = {}
    for onset_tick, _index, event, mapping, note, losses, duration_tick in sorted(entries, key=lambda item: (item[0], item[1])):
        actual_channel = None
        if mapping is not None and note is not None:
            base_channel = int(mapping["channel"])
            end_tick = onset_tick + duration_tick
            if active_until.get((base_channel, note), -1) <= onset_tick:
                actual_channel = base_channel
            elif "program" in mapping and base_channel != 9:
                program = int(mapping["program"])
                for channel in auxiliaries:
                    owner = auxiliary_programs.get(channel)
                    if owner is not None and owner != program:
                        continue
                    if active_until.get((channel, note), -1) > onset_tick:
                        continue
                    auxiliary_programs[channel] = program
                    actual_channel = channel
                    losses.append("overlap_channel_reassigned")
                    break
            if actual_channel is None:
                losses.append("same_note_overlap_cue_only")
            else:
                active_until[(actual_channel, note)] = end_tick
        plan[event["id"]] = {
            "mapping": mapping, "note": note, "losses": losses,
            "channel": actual_channel, "onset_tick": onset_tick, "duration_tick": duration_tick,
        }
    return plan

def export_smf(score: dict[str, Any], registry: dict[str, dict[str, Any]], profile: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    validate_score(score, registry)
    tpq = profile["ticks_per_quarter"]
    tempo_bpm = float(score.get("tempo_bpm", 120))
    tempo_us = _round_half_up(60_000_000.0 / tempo_bpm)
    if not 1 <= tempo_us <= 0xFFFFFF:
        raise ValidationError("tempo is outside the range representable by an SMF tempo meta event")

    conductor = [
        (0, 0, _meta(0x03, _ascii_text(score["title"]))),
        (0, 1, _meta(0x51, tempo_us.to_bytes(3, "big"))),
    ]
    cue_events: list[tuple[int, int, bytes]] = [(0, 0, _meta(0x03, b"ESN Semantic Cues"))]
    source_tracks: dict[str, list[tuple[int, int, bytes]]] = {}
    programmed_channels: set[tuple[str, int]] = set()
    report_events: list[dict[str, Any]] = []
    plan = _midi_plan(score, profile)

    for event in score["events"]:
        planned = plan[event["id"]]
        onset_tick, duration_tick = planned["onset_tick"], planned["duration_tick"]
        cue_events.append((onset_tick, 10, _meta(0x07, _event_cue(profile["cue_prefix"], event))))
        mapping, note, losses, channel = planned["mapping"], planned["note"], planned["losses"], planned["channel"]
        row: dict[str, Any] = {"id": event["id"], "status": "cue_only", "losses": list(losses)}
        if mapping is not None:
            row["channel"] = int(mapping["channel"]) if channel is None else channel
        if note is not None and mapping is not None and channel is not None:
            row.update({"status": "midi_note", "note": note})
            velocity = max(1, min(127, _round_half_up(float(event.get("dynamics", 0.75)) * 127.0)))
            track = source_tracks.setdefault(event["source"], [(0, 0, _meta(0x03, _ascii_text(event["source"])))])
            program_key = (event["source"], channel)
            if "program" in mapping and program_key not in programmed_channels:
                track.append((0, 5, bytes([0xC0 | channel, int(mapping["program"])])))
                programmed_channels.add(program_key)
            track.append((onset_tick, 30, bytes([0x90 | channel, note, velocity])))
            track.append((onset_tick + duration_tick, 20, bytes([0x80 | channel, note, 0])))
        report_events.append(row)

    tracks = [_track(conductor)]
    for source in sorted(source_tracks):
        tracks.append(_track(source_tracks[source]))
    tracks.append(_track(cue_events))
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), tpq)
    payload = header + b"".join(tracks)
    report = {
        "format": "esn-midi-report/1",
        "events_total": len(report_events),
        "midi_notes": sum(row["status"] == "midi_note" for row in report_events),
        "cue_only": sum(row["status"] == "cue_only" for row in report_events),
        "events": report_events,
    }
    return payload, report


def write_smf(path: str | Path, score: dict[str, Any], registry: dict[str, dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    payload, report = export_smf(score, registry, profile)
    Path(path).write_bytes(payload)
    return report

def cue_sheet_csv(score: dict[str, Any], registry: dict[str, dict[str, Any]], profile: dict[str, Any]) -> str:
    validate_score(score, registry)
    tempo = float(score.get("tempo_bpm", 120))
    beat_seconds = 60.0 / tempo
    fieldnames = [
        "id", "source", "gesture", "onset_beats", "end_beats",
        "start_seconds", "end_seconds", "duration_seconds", "pitch",
        "dynamics", "articulation", "midi_status", "midi_channel", "midi_note",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    plan = _midi_plan(score, profile)
    for event in sorted(score["events"], key=lambda item: (float(item["onset"]), item["id"])):
        onset = float(event["onset"])
        duration = float(event["duration"])
        planned = plan[event["id"]]
        mapping, note, losses, channel = planned["mapping"], planned["note"], planned["losses"], planned["channel"]
        if note is not None and channel is not None:
            midi_status = "midi_note" + (":" + "+".join(losses) if losses else "")
        elif "same_note_overlap_cue_only" in losses:
            midi_status = "cue_only:same_note_overlap_cue_only"
        else:
            midi_status = losses[0] if losses else "cue_only"
        pitch = ""
        if "pitch" in event:
            key, value = next(iter(event["pitch"].items()))
            pitch = f"{key}:{value}"
        writer.writerow({
            "id": event["id"], "source": event["source"], "gesture": event["gesture"],
            "onset_beats": f"{onset:g}", "end_beats": f"{onset + duration:g}",
            "start_seconds": f"{onset * beat_seconds:.6f}",
            "end_seconds": f"{(onset + duration) * beat_seconds:.6f}",
            "duration_seconds": f"{duration * beat_seconds:.6f}",
            "pitch": pitch,
            "dynamics": f"{float(event.get('dynamics', 0.75)):g}",
            "articulation": event.get("articulation", "normal"),
            "midi_status": midi_status,
            "midi_channel": "" if mapping is None else str((int(mapping["channel"]) if channel is None else channel) + 1),
            "midi_note": "" if note is None else str(note),
        })
    return output.getvalue()


def write_cue_sheet(path: str | Path, score: dict[str, Any], registry: dict[str, dict[str, Any]], profile: dict[str, Any]) -> None:
    Path(path).write_text(cue_sheet_csv(score, registry, profile), encoding="utf-8", newline="\n")


def canonical_report(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
