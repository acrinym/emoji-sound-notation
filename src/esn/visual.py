from __future__ import annotations

import math
import re
from html import escape
from pathlib import Path
from typing import Any

from .model import ValidationError, load_json

VISUAL_KEYS = {"format", "name", "default_mode", "scale", "palettes", "style", "glyphs"}
SCALE_KEYS = {"tonic", "intervals"}
PALETTE_KEYS = {"pitch_class", "scale_degree", "chromatic", "unpitched"}
STYLE_KEYS = {"stroke", "detail"}
GLYPH_KEYS = {"source", "id", "path", "details"}
COLOR_MODES = {"pitch_class", "scale_degree"}
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
TONIC_RE = re.compile(r"^([A-Ga-g])([#b]?)$")
GLYPH_ID_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
SVG_PATH_RE = re.compile(r"^[MmZzLlHhVvCcSsQqTtAa0-9eE+.,\-\s]+$")
NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _only_keys(value: Any, allowed: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{label} contains unknown fields: {sorted(unknown)}")
    return value


def _color(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX_COLOR_RE.fullmatch(value):
        raise ValidationError(f"{label} must be a #RRGGBB color")
    return value.lower()

def tonic_pitch_class(tonic: str) -> int:
    match = TONIC_RE.fullmatch(tonic)
    if not match:
        raise ValidationError(f"invalid visual tonic: {tonic!r}")
    name, accidental = match.groups()
    pitch = NOTE_OFFSETS[name.upper()]
    if accidental == "#":
        pitch += 1
    elif accidental == "b":
        pitch -= 1
    return pitch % 12


def load_visual_profile(path: str | Path, sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    data = load_json(path)
    _only_keys(data, VISUAL_KEYS, "visual profile")
    if data.get("format") != "esn-visual/1":
        raise ValidationError("visual profile format must be 'esn-visual/1'")
    if not isinstance(data.get("name"), str) or not data["name"]:
        raise ValidationError("visual profile name must be a non-empty string")
    default_mode = data.get("default_mode")
    if default_mode not in COLOR_MODES:
        raise ValidationError(f"visual default_mode must be one of {sorted(COLOR_MODES)}")

    scale = _only_keys(data.get("scale"), SCALE_KEYS, "visual scale")
    tonic = scale.get("tonic")
    if not isinstance(tonic, str):
        raise ValidationError("visual scale.tonic must be a pitch-class string")
    tonic_pitch_class(tonic)
    intervals = scale.get("intervals")
    if not isinstance(intervals, list) or not intervals:
        raise ValidationError("visual scale.intervals must be a non-empty array")
    if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= 11 for x in intervals):
        raise ValidationError("visual scale.intervals must contain integers from 0 through 11")
    if intervals != sorted(set(intervals)) or intervals[0] != 0:
        raise ValidationError("visual scale.intervals must be unique, ascending, and start at 0")

    palettes = _only_keys(data.get("palettes"), PALETTE_KEYS, "visual palettes")
    pitch_class = palettes.get("pitch_class")
    degree = palettes.get("scale_degree")
    if not isinstance(pitch_class, list) or len(pitch_class) != 12:
        raise ValidationError("visual palettes.pitch_class must contain exactly 12 colors")
    if not isinstance(degree, list) or len(degree) != len(intervals):
        raise ValidationError("visual palettes.scale_degree length must match scale.intervals")
    normalized_pitch = [_color(value, f"visual palettes.pitch_class[{i}]") for i, value in enumerate(pitch_class)]
    normalized_degree = [_color(value, f"visual palettes.scale_degree[{i}]") for i, value in enumerate(degree)]
    chromatic = _color(palettes.get("chromatic"), "visual palettes.chromatic")
    unpitched = _color(palettes.get("unpitched"), "visual palettes.unpitched")

    style = _only_keys(data.get("style"), STYLE_KEYS, "visual style")
    stroke = _color(style.get("stroke"), "visual style.stroke")
    detail = _color(style.get("detail"), "visual style.detail")

    raw_glyphs = data.get("glyphs")
    if not isinstance(raw_glyphs, list) or not raw_glyphs:
        raise ValidationError("visual glyphs must be a non-empty array")
    glyph_map: dict[str, dict[str, str]] = {}
    glyph_ids: set[str] = set()
    for index, raw in enumerate(raw_glyphs):
        glyph = _only_keys(raw, GLYPH_KEYS, f"visual glyphs[{index}]")
        source = glyph.get("source")
        glyph_id = glyph.get("id")
        path_data = glyph.get("path")
        details = glyph.get("details", "")
        if source not in sources:
            raise ValidationError(f"visual glyphs[{index}].source is not registered: {source!r}")
        if source in glyph_map:
            raise ValidationError(f"duplicate visual glyph source: {source}")
        if not isinstance(glyph_id, str) or not GLYPH_ID_RE.fullmatch(glyph_id):
            raise ValidationError(f"visual glyphs[{index}].id is not a portable glyph id")
        if glyph_id in glyph_ids:
            raise ValidationError(f"duplicate visual glyph id: {glyph_id}")
        if not isinstance(path_data, str) or not path_data or not SVG_PATH_RE.fullmatch(path_data):
            raise ValidationError(f"visual glyphs[{index}].path contains invalid SVG path syntax")
        if not isinstance(details, str) or (details and not SVG_PATH_RE.fullmatch(details)):
            raise ValidationError(f"visual glyphs[{index}].details contains invalid SVG path syntax")
        glyph_ids.add(glyph_id)
        glyph_map[source] = {"id": glyph_id, "path": path_data, "details": details}

    missing = set(sources) - set(glyph_map)
    if missing:
        raise ValidationError(f"visual profile is missing glyph bindings for: {sorted(missing)}")

    return {
        "format": "esn-visual/1",
        "name": data["name"],
        "default_mode": default_mode,
        "scale": {"tonic": tonic, "intervals": intervals},
        "palettes": {
            "pitch_class": normalized_pitch,
            "scale_degree": normalized_degree,
            "chromatic": chromatic,
            "unpitched": unpitched,
        },
        "style": {"stroke": stroke, "detail": detail},
        "glyphs": glyph_map,
    }


def color_cue_for_midi(profile: dict[str, Any], midi: float, mode: str | None = None) -> tuple[str, str]:
    selected = mode or profile["default_mode"]
    if selected not in COLOR_MODES:
        raise ValidationError(f"visual color mode must be one of {sorted(COLOR_MODES)}")
    pitch_class = math.floor(midi + 0.5) % 12
    if selected == "pitch_class":
        return profile["palettes"]["pitch_class"][pitch_class], f"pitch class {PC_NAMES[pitch_class]}"

    tonic_pc = tonic_pitch_class(profile["scale"]["tonic"])
    relative = (pitch_class - tonic_pc) % 12
    intervals = profile["scale"]["intervals"]
    if relative not in intervals:
        return profile["palettes"]["chromatic"], "chromatic outside configured scale"
    degree = intervals.index(relative)
    return profile["palettes"]["scale_degree"][degree], f"scale degree {degree + 1}"


def glyph_svg(profile: dict[str, Any], source_id: str, x: float, y: float, size: float, color: str) -> str:
    glyph = profile["glyphs"].get(source_id)
    if glyph is None:
        raise ValidationError(f"visual glyph not found for source: {source_id}")
    scale = size / 24.0
    stroke = profile["style"]["stroke"]
    detail = profile["style"]["detail"]
    details = ""
    if glyph["details"]:
        details = (
            f'<path d="{escape(glyph["details"])}" fill="none" stroke="{detail}" '
            'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    return (
        f'<g transform="translate({x:.2f} {y:.2f}) scale({scale:.5f})">'
        f'<path d="{escape(glyph["path"])}" fill="{color}" stroke="{stroke}" '
        'stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'{details}</g>'
    )

def render_glyph_sheet(profile: dict[str, Any], sources: dict[str, dict[str, Any]]) -> str:
    source_ids = list(sources)
    pitch_colors = profile["palettes"]["pitch_class"]
    degree_colors = profile["palettes"]["scale_degree"]
    columns = max(len(pitch_colors), len(degree_colors))
    left = 190
    cell = 54
    section_gap = 54
    row_height = 48
    width = left + columns * cell + 40
    pitch_top = 86
    degree_top = pitch_top + len(source_ids) * row_height + section_gap
    height = degree_top + len(source_ids) * row_height + 70
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<title>ESN Core Canonical Glyph Colorways</title>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="34" font-family="sans-serif" font-size="22" font-weight="700">ESN canonical glyph colorways</text>',
        '<text x="24" y="57" font-family="sans-serif" font-size="12">Custom in-house SVG geometry · tintable independently of platform emoji artwork</text>',
    ]

    def section(title: str, top: int, colors: list[str]) -> None:
        parts.append(f'<text x="24" y="{top - 20}" font-family="sans-serif" font-size="14" font-weight="700">{escape(title)}</text>')
        for index, color in enumerate(colors):
            x = left + index * cell
            parts.append(f'<rect x="{x}" y="{top - 15}" width="32" height="8" rx="4" fill="{color}"/>')
        for row, source_id in enumerate(source_ids):
            y = top + row * row_height
            parts.append(f'<text x="24" y="{y + 25}" font-family="sans-serif" font-size="12">{escape(source_id)}</text>')
            for index, color in enumerate(colors):
                x = left + index * cell
                parts.append(glyph_svg(profile, source_id, x, y, 32, color))

    section("Absolute pitch-class palette", pitch_top, pitch_colors)
    section(
        f'Relative scale-degree palette · tonic {profile["scale"]["tonic"]}',
        degree_top,
        degree_colors,
    )
    parts.append('</svg>')
    return "\n".join(parts) + "\n"
