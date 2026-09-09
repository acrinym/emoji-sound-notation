from __future__ import annotations

from html import escape
from typing import Any

from .model import pitch_to_midi

PITCH_COLORS = [
    "#e74c3c", "#e67e22", "#f1c40f", "#9acd32",
    "#2ecc71", "#1abc9c", "#00a8cc", "#3498db",
    "#5b6ee1", "#8e44ad", "#c039d3", "#e84393",
]


def _pitch_class(midi: float) -> int:
    return int(round(midi)) % 12


def _event_midis(event: dict[str, Any]) -> list[float]:
    if "pitch" not in event:
        return []
    values = [pitch_to_midi(event["pitch"])]
    for point in event.get("pitch_curve", []):
        values.append(pitch_to_midi(point["pitch"]))
    return values


def render_svg(score: dict[str, Any], registry: dict[str, dict[str, Any]]) -> str:
    events = score["events"]
    all_midis = [m for event in events for m in _event_midis(event)]
    low = min(all_midis, default=48.0) - 2
    high = max(all_midis, default=72.0) + 2
    beat_width = 110.0
    pitch_step = 10.0
    left = 150.0
    top = 70.0
    pitched_height = max(180.0, (high - low) * pitch_step)
    unpitched_sources = sorted({event["source"] for event in events if "pitch" not in event})
    lane_height = 54.0
    unpitched_top = top + pitched_height + 70.0
    max_end = max((float(e["onset"]) + float(e["duration"]) for e in events), default=4.0)
    width = max(900.0, left + max_end * beat_width + 100.0)
    height = unpitched_top + max(1, len(unpitched_sources)) * lane_height + 80.0

    def y_for_midi(midi: float) -> float:
        return top + (high - midi) * pitch_step

    lanes = {source_id: unpitched_top + i * lane_height for i, source_id in enumerate(unpitched_sources)}
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" role="img">',
        f'<title>{escape(score["title"])}</title>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="24" y="36" font-family="sans-serif" font-size="22" font-weight="700">{escape(score["title"])}</text>',
        '<text x="24" y="58" font-family="sans-serif" font-size="12">ESN/1 · X=time · Y=pitch · color=absolute pitch class · text labels are redundant accessibility encoding</text>',
    ]

    beat = 0
    while beat <= int(max_end) + 1:
        x = left + beat * beat_width
        parts.append(f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{height - 45:.1f}" stroke="#e5e5e5"/>')
        parts.append(f'<text x="{x + 3:.1f}" y="{top - 10:.1f}" font-family="sans-serif" font-size="10">{beat}</text>')
        beat += 1
    for source_id, y in lanes.items():
        glyph = registry[source_id]["glyph"]
        parts.append(f'<line x1="{left:.1f}" y1="{y + 24:.1f}" x2="{width - 40:.1f}" y2="{y + 24:.1f}" stroke="#eeeeee"/>')
        parts.append(f'<text x="24" y="{y + 29:.1f}" font-family="sans-serif" font-size="14">{escape(glyph)} {escape(source_id)}</text>')

    for event in events:
        source = registry[event["source"]]
        glyph = escape(source["glyph"])
        onset = float(event["onset"])
        duration = float(event["duration"])
        dynamics = float(event.get("dynamics", 0.75))
        x = left + onset * beat_width
        event_width = max(20.0, duration * beat_width)
        label = f'{event["source"]} / {event["gesture"]}'
        if "pitch" in event:
            midi = pitch_to_midi(event["pitch"])
            y = y_for_midi(midi)
            color = PITCH_COLORS[_pitch_class(midi)]
            points = [(x, y)]
            for point in event.get("pitch_curve", []):
                px = x + float(point["at"]) * event_width
                py = y_for_midi(pitch_to_midi(point["pitch"]))
                points.append((px, py))
            points.append((x + event_width, points[-1][1]))
            point_text = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
            stroke_width = 2.0 + dynamics * 6.0
            parts.append(f'<polyline points="{point_text}" fill="none" stroke="{color}" stroke-width="{stroke_width:.1f}" stroke-linecap="round"/>')
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{13 + dynamics * 7:.1f}" fill="{color}" fill-opacity="0.28" stroke="{color}"/>')
            pitch_text = next(iter(event["pitch"].values()))
            parts.append(f'<text x="{x - 9:.1f}" y="{y + 6:.1f}" font-family="Segoe UI Emoji, sans-serif" font-size="20">{glyph}</text>')
            parts.append(f'<text x="{x + 18:.1f}" y="{y - 8:.1f}" font-family="sans-serif" font-size="10">{escape(str(pitch_text))} · {escape(label)}</text>')
        else:
            y = lanes[event["source"]] + 24.0
            bar_height = 8.0 + dynamics * 14.0
            parts.append(f'<rect x="{x:.1f}" y="{y - bar_height/2:.1f}" width="{event_width:.1f}" height="{bar_height:.1f}" rx="5" fill="#555" fill-opacity="0.28" stroke="#333"/>')
            parts.append(f'<text x="{x + 4:.1f}" y="{y + 6:.1f}" font-family="Segoe UI Emoji, sans-serif" font-size="20">{glyph}</text>')
            parts.append(f'<text x="{x + 30:.1f}" y="{y - 8:.1f}" font-family="sans-serif" font-size="10">unpitched · {escape(label)}</text>')

        event_label = escape(f'{event["id"]}: {label}; onset {onset:g}; duration {duration:g}; dynamics {dynamics:g}')
        parts.append(f'<desc>{event_label}</desc>')

    parts.append(f'<line x1="{left:.1f}" y1="{unpitched_top - 28:.1f}" x2="{width - 40:.1f}" y2="{unpitched_top - 28:.1f}" stroke="#999" stroke-dasharray="4 4"/>')
    parts.append(f'<text x="24" y="{unpitched_top - 23:.1f}" font-family="sans-serif" font-size="11" font-weight="700">UNPITCHED / SPECTRAL EVENTS</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"
