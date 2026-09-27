"""Export Engine — serialises Scene → versioned JSON for web dashboard."""

from __future__ import annotations
from typing import Dict, Any
from enum import Enum

from .scene import Scene, LayerType


def scene_to_json(scene: Scene) -> Dict[str, Any]:
    """Serialize Scene to a versioned JSON-compatible dict."""
    out = {
        "scene_version": 2,
        "metadata": dict(scene.metadata),
        "viewport": {
            "candle_first": scene.viewport.candle_first,
            "candle_last": scene.viewport.candle_last,
            "price_min": scene.viewport.price_min,
            "price_max": scene.viewport.price_max,
            "candle_count": scene.viewport.candle_count,
            "price_range": scene.viewport.price_range,
        },
        "layers": [],
    }

    for layer in scene.layers:
        layer_data = {
            "type": layer.type.name,
            "visible": layer.visible,
            "elements": [],
        }
        for el in layer.elements:
            el_data = {
                "type": el.element_type.name,
                "layer": el.layer.name,
                "direction": el.direction.name if el.direction else None,
                "label": el.label,
                "priority": el.priority,
                "collision_policy": el.collision_policy.name,
                "bbox": {
                    "price_high": el.bbox.price_high,
                    "price_low": el.bbox.price_low,
                    "candle_start": el.bbox.candle_start,
                    "candle_end": el.bbox.candle_end,
                },
                "data": dict(el.data) if el.data else {},
            }

            if el.kind is not None:
                kind = el.kind
                if isinstance(kind, Enum):
                    el_data["kind"] = kind.name
                else:
                    el_data["kind"] = str(kind)

            layer_data["elements"].append(el_data)

        out["layers"].append(layer_data)

    return out
