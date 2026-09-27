"""Scene graph — pure immutable data models.

Every element is a frozen dataclass. No rendering logic, no PIL, no drawing.
Backends read these models and produce output.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union

from .enums import (
    LayerType, ElementType, StructureKind, LiquidityKind,
    SwingKind, TradeKind, Direction, CollisionPolicy,
)


# ── Spatial ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class BoundingBox:
    price_high: float
    price_low: float
    candle_start: int
    candle_end: int

    @property
    def price_span(self) -> float:
        return self.price_high - self.price_low

    @property
    def candle_span(self) -> int:
        return max(0, self.candle_end - self.candle_start)

    def overlaps(self, other: BoundingBox) -> bool:
        price_overlap = (self.price_low <= other.price_high and
                         other.price_low <= self.price_high)
        candle_overlap = (self.candle_start <= other.candle_end and
                          other.candle_start <= self.candle_end)
        return price_overlap and candle_overlap

    def merge(self, other: BoundingBox) -> BoundingBox:
        return BoundingBox(
            price_high=max(self.price_high, other.price_high),
            price_low=min(self.price_low, other.price_low),
            candle_start=min(self.candle_start, other.candle_start),
            candle_end=max(self.candle_end, other.candle_end),
        )


# ── Visual properties ────────────────────────────────────────────
@dataclass(frozen=True)
class VisualProps:
    color: Optional[str] = None
    fill_alpha: Optional[float] = None
    line_width: Optional[float] = None
    line_style: Optional[str] = None
    font_size: Optional[int] = None
    radius: Optional[int] = None
    padding: Optional[int] = None


# ── Element ──────────────────────────────────────────────────────
_ElementKind = Union[StructureKind, LiquidityKind, SwingKind,
                     TradeKind, Direction, str, None]


@dataclass(frozen=True)
class Element:
    """Single scene element — pure data, no drawing logic.

    Use `kind` for sub-typing (BOS vs CHOCH, ENTRY vs SL, etc.)
    instead of creating separate classes.
    """
    element_type: ElementType
    layer: LayerType
    bbox: BoundingBox
    kind: Any = None            # sub-type discriminator
    direction: Direction = Direction.NEUTRAL
    label: str = ""
    priority: int = 5
    collision_policy: CollisionPolicy = CollisionPolicy.HIDE
    visual: Optional[VisualProps] = None
    data: Dict[str, Any] = field(default_factory=dict)


# ── Scene ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Layer:
    type: LayerType
    elements: List[Element]
    visible: bool = True
    blend_mode: str = "normal"


@dataclass(frozen=True)
class Viewport:
    candle_first: int = 0
    candle_last: int = 0
    price_min: float = 0.0
    price_max: float = 0.0

    @property
    def candle_count(self) -> int:
        return max(1, self.candle_last - self.candle_first + 1)

    @property
    def price_range(self) -> float:
        return max(0.01, self.price_max - self.price_min)


@dataclass(frozen=True)
class Scene:
    metadata: Dict[str, Any]
    viewport: Viewport
    layers: List[Layer]

    @property
    def all_elements(self) -> List[Element]:
        result = []
        for layer in self.layers:
            if layer.visible:
                result.extend(layer.elements)
        return result
