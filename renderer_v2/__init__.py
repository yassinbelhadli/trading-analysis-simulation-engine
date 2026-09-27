"""Renderer V2 — Scene-based render pipeline.

Usage:
    from renderer_v2 import render_snapshot

    img = render_snapshot(snapshot_dict, output_path="chart.png")

Architecture:
    Snapshot → Builders → Scene → Layout → Collision → Backend → Output

Scene = pure data (no PIL, no drawing)
Layout = data-to-pixel mapping (CoordMapper)
Collision = overlap resolution with policies
Backend = plug-in (PIL, matplotlib, web, SVG)
"""

from __future__ import annotations
from typing import Optional, Dict, Any

from .builder import build_scene
from .layout import layout_scene, PixelBounds
from .backends.pil import PILBackend
from .theme import Theme, DARK_THEME, LIGHT_THEME
from .export import scene_to_json


def render_snapshot(
    snapshot: Dict[str, Any],
    output_path: Optional[str] = None,
    theme: Optional[Theme] = None,
    width: int = 1200,
    height: int = 600,
    explanation: Optional[Any] = None,
    backend: Optional["PILBackend"] = None,
    minimal: bool = False,
) -> "Image":
    """One-shot convenience: snapshot dict → rendered PIL Image.

    Args:
        snapshot: dict from detection engine (setup_detector.to_snapshot()
                  or ict_analysis.build_snapshot())
        output_path: optional file path to save PNG
        theme: Theme instance (default: DARK_THEME)
        width: chart area pixel width
        height: chart area pixel height
        explanation: optional Explanation from explainability engine.
                     If provided, its data enriches scene annotations
                     (reasons, confidence, invalidations).
        backend: optional PILBackend instance (used by QA to inspect
                 drawn label boxes after rendering).
        minimal: if True, render only candles + Entry/SL/TP levels (used
                 for clean Telegram signal charts); every other overlay
                 (structure, liquidity, FVG, OB, zones, current price) is
                 dropped.

    Returns:
        PIL Image
    """
    theme = theme or DARK_THEME

    # Inject explanation data into snapshot for builders
    if explanation is not None:
        if "scoring" not in snapshot or not snapshot["scoring"]:
            snapshot["scoring"] = {}
        snapshot["scoring"]["explain_verdict"] = explanation.verdict
        snapshot["scoring"]["explain_confidence"] = explanation.confidence
        snapshot["scoring"]["explain_reasons_passed"] = [
            {"code": r.code.value, "label": _reason_label(r.code), "weight": r.weight}
            for r in explanation.passed_reasons
        ]
        snapshot["scoring"]["explain_reasons_failed"] = [
            {"code": r.code.value, "label": _reason_label(r.code), "weight": r.weight}
            for r in explanation.failed_reasons
        ]
        snapshot["scoring"]["explain_warnings"] = [
            {"message": w.message, "severity": w.severity}
            for w in explanation.warnings
        ]
        snapshot["scoring"]["explain_invalidations"] = [
            {"description": inv.description, "trigger_price": inv.trigger_price}
            for inv in explanation.invalidations
        ]

    scene = build_scene(snapshot, theme, minimal=minimal)

    vp = scene.viewport
    px_bounds = PixelBounds(
        top=0,
        bottom=float(height),
        left=0,
        right=float(width),
        width=float(width),
        height=float(height),
    )

    layout = layout_scene(scene, px_bounds, theme)
    backend = backend or PILBackend(theme)
    return backend.render(layout, output_path)


def _reason_label(code: str) -> str:
    from core_engine.explainability.formatter import reason_label as rl
    from core_engine.explainability.reason_codes import ReasonCode
    try:
        return rl(ReasonCode(code))
    except (ValueError, Exception):
        return code


def snapshot_to_json(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot dict → versioned JSON for web dashboard."""
    scene = build_scene(snapshot)
    return scene_to_json(scene)


def available_themes() -> list:
    return ["dark", "light"]


__all__ = [
    "render_snapshot",
    "snapshot_to_json",
    "build_scene",
    "layout_scene",
    "PILBackend",
    "Theme", "DARK_THEME", "LIGHT_THEME",
    "available_themes",
]
