"""LayoutEngine — applies CoordMapper to every element's BoundingBox.

Produces a LayoutScene where every element has pixel coordinates resolved.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any

from .scene import Scene, Element, Layer, LayerType, BoundingBox
from .mapper import CoordMapper, PixelBounds
from .theme import Theme


@dataclass(frozen=True)
class LayoutElement:
    element: Element
    px_top: float
    px_bottom: float
    px_left: float
    px_right: float
    px_center_x: float
    px_center_y: float
    visible: bool = True

    @property
    def width(self) -> float:
        return self.px_right - self.px_left

    @property
    def height(self) -> float:
        return self.px_bottom - self.px_top

    def bbox_px(self) -> tuple:
        return (self.px_left, self.px_top, self.px_right, self.px_bottom)


@dataclass(frozen=True)
class LayoutLayer:
    type: LayerType
    elements: List[LayoutElement]
    visible: bool = True


@dataclass(frozen=True)
class LayoutScene:
    metadata: Dict[str, Any]
    mapper: CoordMapper
    theme: Theme
    layers: List[LayoutLayer]

    @property
    def all_elements(self) -> List[LayoutElement]:
        result = []
        for layer in self.layers:
            if layer.visible:
                result.extend(layer.elements)
        return result

    def elements_by_type(self, type_name: str) -> List[LayoutElement]:
        return [e for e in self.all_elements
                if e.element.element_type.name == type_name]


def layout_scene(scene: Scene, px_bounds: PixelBounds,
                 theme: Theme = None) -> LayoutScene:
    """Convert data-coordinate Scene into pixel-coordinate LayoutScene."""
    mapper = CoordMapper(viewport=scene.viewport, bounds=px_bounds)
    theme = theme or Theme()

    layout_layers = []
    for layer in scene.layers:
        laid = []
        for el in layer.elements:
            px_top = mapper.y_of(el.bbox.price_high)
            px_bottom = mapper.y_of(el.bbox.price_low)
            px_left = mapper.x_of(el.bbox.candle_start)
            px_right = mapper.x_of(el.bbox.candle_end)
            laid.append(LayoutElement(
                element=el,
                px_top=px_top,
                px_bottom=px_bottom,
                px_left=px_left,
                px_right=px_right,
                px_center_x=(px_left + px_right) / 2,
                px_center_y=(px_top + px_bottom) / 2,
            ))
        layout_layers.append(LayoutLayer(
            type=layer.type,
            elements=laid,
            visible=layer.visible,
        ))

    return LayoutScene(
        metadata=scene.metadata,
        mapper=mapper,
        theme=theme or Theme(),
        layers=layout_layers,
    )
