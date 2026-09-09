from __future__ import annotations

import hashlib
import math
import random
import struct
import wave
from io import BytesIO
from pathlib import Path
from typing import Any

from .model import ValidationError, load_json, pitch_to_midi, validate_score

PLAYBACK_KEYS = {"format", "sample_rate", "seed", "profiles"}
PROFILE_KEYS = {
    "source", "gesture", "mode", "wave", "gain", "attack", "release",
    "noise_shape", "base_hz",
}
MODES = {"oscillator", "noise", "impulse"}
WAVES = {"sine", "triangle", "square", "saw"}
NOISE_SHAPES = {"white", "soft"}


def midi_to_hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def _number(value: Any, label: str, *, low: float | None = None, high: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError(f"{label} must be finite")
    if low is not None and result < low:
        raise ValidationError(f"{label} must be >= {low}")
    if high is not None and result > high:
        raise ValidationError(f"{label} must be <= {high}")
    return result


def load_playback_registry(path: str | Path, sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    data = load_json(path)
    unknown = set(data) - PLAYBACK_KEYS
    if unknown:
        raise ValidationError(f"playback registry contains unknown fields: {sorted(unknown)}")
    if data.get("format") != "esn-playback/1":
        raise ValidationError("playback registry format must be 'esn-playback/1'")
    sample_rate = data.get("sample_rate", 22050)
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or not 8000 <= sample_rate <= 96000:
        raise ValidationError("playback sample_rate must be an integer from 8000 through 96000")
    seed = data.get("seed", 0)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValidationError("playback seed must be an integer")
    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ValidationError("playback profiles must be a non-empty array")

    profiles: dict[tuple[str, str], dict[str, Any]] = {}
    for index, profile in enumerate(raw_profiles):
        where = f"playback.profiles[{index}]"
        if not isinstance(profile, dict):
            raise ValidationError(f"{where} must be an object")
        extras = set(profile) - PROFILE_KEYS
        if extras:
            raise ValidationError(f"{where} contains unknown fields: {sorted(extras)}")
        source_id = profile.get("source")
        gesture = profile.get("gesture")
        mode = profile.get("mode")
        if source_id not in sources:
            raise ValidationError(f"{where}.source is not registered: {source_id!r}")
        if gesture != "*" and gesture not in sources[source_id]["gestures"]:
            raise ValidationError(f"{where}.gesture is not valid for {source_id}")
        if mode not in MODES:
            raise ValidationError(f"{where}.mode must be one of {sorted(MODES)}")
        if mode == "oscillator" and profile.get("wave", "sine") not in WAVES:
            raise ValidationError(f"{where}.wave must be one of {sorted(WAVES)}")
        if mode == "noise" and profile.get("noise_shape", "white") not in NOISE_SHAPES:
            raise ValidationError(f"{where}.noise_shape must be one of {sorted(NOISE_SHAPES)}")
        _number(profile.get("gain", 0.7), f"{where}.gain", low=0, high=1)
        _number(profile.get("attack", 0.01), f"{where}.attack", low=0, high=10)
        _number(profile.get("release", 0.05), f"{where}.release", low=0, high=10)
        _number(profile.get("base_hz", 440.0), f"{where}.base_hz", low=1, high=24000)
        key = (source_id, gesture)
        if key in profiles:
            raise ValidationError(f"duplicate playback profile for {source_id}/{gesture}")
        profiles[key] = profile
    return {"sample_rate": sample_rate, "seed": seed, "profiles": profiles}


def resolve_profile(playback: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    profiles = playback["profiles"]
    exact = (event["source"], event["gesture"])
    fallback = (event["source"], "*")
    profile = profiles.get(exact) or profiles.get(fallback)
    if profile is None:
        raise ValidationError(f"no playback profile for {event['source']}/{event['gesture']}")
    return profile


def _midi_at(event: dict[str, Any], at: float) -> float | None:
    if "pitch" not in event:
        return None
    controls = [(0.0, pitch_to_midi(event["pitch"]))]
    controls.extend((float(point["at"]), pitch_to_midi(point["pitch"])) for point in event.get("pitch_curve", []))
    if controls[-1][0] < 1.0:
        controls.append((1.0, controls[-1][1]))
    for (left_at, left_midi), (right_at, right_midi) in zip(controls, controls[1:]):
        if at <= right_at:
            span = right_at - left_at
            ratio = 0.0 if span <= 0 else (at - left_at) / span
            return left_midi + (right_midi - left_midi) * max(0.0, min(1.0, ratio))
    return controls[-1][1]


def _wave_value(kind: str, phase: float) -> float:
    unit = (phase / (2.0 * math.pi)) % 1.0
    if kind == "sine":
        return math.sin(phase)
    if kind == "square":
        return 1.0 if unit < 0.5 else -1.0
    if kind == "saw":
        return 2.0 * unit - 1.0
    return 2.0 * abs(2.0 * unit - 1.0) - 1.0


def _event_seed(global_seed: int, event_id: str) -> int:
    digest = hashlib.sha256(f"{global_seed}:{event_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def render_wav(score: dict[str, Any], sources: dict[str, dict[str, Any]], playback: dict[str, Any]) -> bytes:
    validate_score(score, sources)
    sample_rate = playback["sample_rate"]
    beat_seconds = 60.0 / float(score.get("tempo_bpm", 120))
    resolved = [(event, resolve_profile(playback, event)) for event in score["events"]]
    max_seconds = 0.25
    for event, profile in resolved:
        end = (float(event["onset"]) + float(event["duration"])) * beat_seconds
        max_seconds = max(max_seconds, end + float(profile.get("release", 0.05)))
    samples = [0.0] * (int(math.ceil(max_seconds * sample_rate)) + 1)

    for event, profile in resolved:
        onset_s = float(event["onset"]) * beat_seconds
        duration_s = float(event["duration"]) * beat_seconds
        attack = float(profile.get("attack", 0.01))
        release = float(profile.get("release", 0.05))
        gain = float(profile.get("gain", 0.7)) * float(event.get("dynamics", 0.75))
        start = int(round(onset_s * sample_rate))
        count = max(1, int(math.ceil((duration_s + release) * sample_rate)))
        mode = profile["mode"]
        rng = random.Random(_event_seed(playback["seed"], event["id"]))
        phase = 0.0
        soft_noise = 0.0

        for offset in range(count):
            local_s = offset / sample_rate
            if local_s < duration_s:
                attack_env = 1.0 if attack <= 0 else min(1.0, local_s / attack)
                envelope = attack_env
            else:
                tail = local_s - duration_s
                envelope = 0.0 if release <= 0 else max(0.0, 1.0 - tail / release)
            if envelope <= 0:
                continue

            if mode == "oscillator":
                at = min(1.0, local_s / duration_s) if duration_s > 0 else 1.0
                midi = _midi_at(event, at)
                hz = midi_to_hz(midi) if midi is not None else float(profile.get("base_hz", 440.0))
                phase += 2.0 * math.pi * hz / sample_rate
                signal = _wave_value(profile.get("wave", "sine"), phase)
            elif mode == "noise":
                raw = rng.uniform(-1.0, 1.0)
                if profile.get("noise_shape", "white") == "soft":
                    soft_noise = 0.88 * soft_noise + 0.12 * raw
                    signal = soft_noise * 2.2
                else:
                    signal = raw
            else:
                raw = rng.uniform(-1.0, 1.0)
                signal = raw * math.exp(-18.0 * local_s)

            index = start + offset
            if index < len(samples):
                samples[index] += signal * envelope * gain

    pcm = bytearray()
    for value in samples:
        clipped = max(-1.0, min(1.0, value))
        pcm.extend(struct.pack("<h", int(round(clipped * 32767.0))))

    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(pcm))
    return output.getvalue()


def write_wav(path: str | Path, score: dict[str, Any], sources: dict[str, dict[str, Any]], playback: dict[str, Any]) -> None:
    Path(path).write_bytes(render_wav(score, sources, playback))
