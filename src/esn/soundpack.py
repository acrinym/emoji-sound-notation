from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from .model import ValidationError, load_json, pitch_to_midi

PACK_KEYS = {"format", "id", "name", "version", "license", "provenance", "fallback", "bindings"}
LICENSE_KEYS = {"name", "spdx", "url"}
PROVENANCE_KEYS = {"creator", "source", "notes"}
BINDING_KEYS = {"source", "gesture", "asset", "gain", "loop", "root_note", "credit"}


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def _object(value: Any, label: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    extras = set(value) - allowed
    if extras:
        raise ValidationError(f"{label} contains unknown fields: {sorted(extras)}")
    missing = required - set(value)
    if missing:
        raise ValidationError(f"{label} is missing required fields: {sorted(missing)}")
    return value


def _gain(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValidationError(f"{label} must be numeric")
    result = float(value)
    if not 0 <= result <= 4:
        raise ValidationError(f"{label} must be between 0 and 4")
    return result


def _asset_path(root: Path, value: Any, label: str) -> tuple[str, Path]:
    asset = _nonempty(value, label).replace("\\", "/")
    relative = Path(asset)
    windows_drive = re.match(r"^[A-Za-z]:", asset) is not None
    if relative.is_absolute() or windows_drive or asset.startswith("/") or ".." in relative.parts or relative.suffix.lower() != ".wav":
        raise ValidationError(f"{label} must be a relative .wav path without traversal")
    root_resolved = root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValidationError(f"{label} escapes the sound-pack folder") from exc
    return asset, resolved


def load_sound_pack(path: str | Path, sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    manifest_path = Path(path)
    data = load_json(manifest_path)
    _object(data, "sound pack", PACK_KEYS, PACK_KEYS)
    if data.get("format") != "esn-sound-pack/1":
        raise ValidationError("sound pack format must be 'esn-sound-pack/1'")
    for key in ("id", "name", "version"):
        _nonempty(data.get(key), f"sound pack {key}")
    if data.get("fallback") != "reference_synth":
        raise ValidationError("sound pack fallback must be 'reference_synth'")

    license_doc = _object(data.get("license"), "sound pack license", LICENSE_KEYS, {"name"})
    _nonempty(license_doc.get("name"), "sound pack license.name")
    for key in set(license_doc) - {"name"}:
        _nonempty(license_doc.get(key), f"sound pack license.{key}")

    provenance = _object(data.get("provenance"), "sound pack provenance", PROVENANCE_KEYS, {"creator"})
    _nonempty(provenance.get("creator"), "sound pack provenance.creator")
    for key in set(provenance) - {"creator", "notes"}:
        _nonempty(provenance.get(key), f"sound pack provenance.{key}")
    if "notes" in provenance and not isinstance(provenance["notes"], str):
        raise ValidationError("sound pack provenance.notes must be a string")

    raw_bindings = data.get("bindings")
    if not isinstance(raw_bindings, list):
        raise ValidationError("sound pack bindings must be an array")

    bindings: dict[tuple[str, str], dict[str, Any]] = {}
    missing_assets: list[str] = []
    root = manifest_path.resolve().parent
    for index, binding in enumerate(raw_bindings):
        where = f"sound pack bindings[{index}]"
        binding = _object(binding, where, BINDING_KEYS, {"source", "gesture", "asset"})
        source_id = binding.get("source")
        gesture = binding.get("gesture")
        if source_id not in sources:
            raise ValidationError(f"{where}.source is not registered: {source_id!r}")
        if gesture != "*" and gesture not in sources[source_id]["gestures"]:
            raise ValidationError(f"{where}.gesture is not valid for {source_id}")
        asset, resolved_asset = _asset_path(root, binding.get("asset"), f"{where}.asset")
        binding["asset"] = asset
        if "gain" in binding:
            _gain(binding["gain"], f"{where}.gain")
        if "loop" in binding and not isinstance(binding["loop"], bool):
            raise ValidationError(f"{where}.loop must be boolean")
        if "root_note" in binding:
            root_note = _nonempty(binding["root_note"], f"{where}.root_note")
            try:
                pitch_to_midi({"note": root_note})
            except ValidationError as exc:
                raise ValidationError(f"{where}.root_note is invalid: {root_note}") from exc
        if "credit" in binding and not isinstance(binding["credit"], str):
            raise ValidationError(f"{where}.credit must be a string")
        key = (source_id, gesture)
        if key in bindings:
            raise ValidationError(f"duplicate sound-pack binding for {source_id}/{gesture}")
        bindings[key] = dict(binding)
        if not resolved_asset.is_file():
            missing_assets.append(asset)

    return {
        "doc": data,
        "root": root,
        "bindings": bindings,
        "missing_assets": tuple(sorted(missing_assets)),
    }


def resolve_sound_binding(sound_pack: dict[str, Any], event: dict[str, Any]) -> dict[str, Any] | None:
    bindings = sound_pack["bindings"]
    return bindings.get((event["source"], event["gesture"])) or bindings.get((event["source"], "*"))


def binding_asset_path(sound_pack: dict[str, Any], binding: dict[str, Any]) -> Path:
    _, resolved = _asset_path(sound_pack["root"], binding["asset"], "sound pack binding asset")
    return resolved
