"""CollisionResolver — detects overlapping layout elements and resolves via policies.

Iterative multi-pass: detect → shift → detect → shift (up to N iterations).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from copy import deepcopy

from .scene import CollisionPolicy, Layer, Element, LayerType
from .layout import LayoutScene, LayoutElement, LayoutLayer


def _rects_overlap(a: Tuple[float, float, float, float],
                   b: Tuple[float, float, float, float]) -> bool:
    """Check overlap of two (left, top, right, bottom) pixel rects."""
    return (a[0] < b[2] and b[0] < a[2] and
            a[1] < b[3] and b[1] < a[3])


@dataclass(frozen=True)
class ResolvedScene:
    """Final scene after collision resolution — some elements may be hidden/moved."""
    metadata: dict
    elements: List[LayoutElement]


@dataclass
class _SpatialBucket:
    x: int
    y: int
    elements: List[int] = field(default_factory=list)


class CollisionResolver:
    """Spatial-hash based collision resolver with iterative multi-pass resolution.

    Iterations: up to MAX_PASSES — each pass detects overlaps, shifts lower-priority
    elements down by 20px, then re-checks. Elements that still overlap after all
    passes are hidden.
    """

    MAX_PASSES = 5

    def resolve(self, layout: LayoutScene,
                default_policy: CollisionPolicy = CollisionPolicy.HIDE) -> ResolvedScene:
        """Detect and resolve collisions across all visible layers (multi-pass)."""
        elements = list(layout.all_elements)

        for _pass in range(self.MAX_PASSES):
            conflicts = self._detect_all(elements)
            if not conflicts:
                break

            # Apply shifts
            for idx, nidx in conflicts:
                el = elements[idx]
                nel = elements[nidx]

                policy = el.element.collision_policy
                n_policy = nel.element.collision_policy

                if policy == CollisionPolicy.NONE or n_policy == CollisionPolicy.NONE:
                    continue
                if (el.element.layer == LayerType.CANDLES or
                        nel.element.layer == LayerType.CANDLES):
                    continue

                # Shift the lower-priority element out of the way.
                if el.element.priority < nel.element.priority:
                    elements[idx] = self._shift(el)
                else:
                    elements[nidx] = self._shift(nel)

        # After all passes, hide any still-overlapping elements
        final_conflicts = self._detect_all(elements)
        hidden_indices = set()
        for idx, nidx in final_conflicts:
            el = elements[idx]
            nel = elements[nidx]
            if el.element.layer == LayerType.CANDLES or nel.element.layer == LayerType.CANDLES:
                continue
            if el.element.collision_policy == CollisionPolicy.NONE or nel.element.collision_policy == CollisionPolicy.NONE:
                continue
            # Hide the lower-priority element; keep the important one.
            if el.element.priority < nel.element.priority:
                hidden_indices.add(idx)
            else:
                hidden_indices.add(nidx)

        result = []
        for i, el in enumerate(elements):
            result.append(LayoutElement(
                element=el.element,
                px_top=el.px_top,
                px_bottom=el.px_bottom,
                px_left=el.px_left,
                px_right=el.px_right,
                px_center_x=el.px_center_x,
                px_center_y=el.px_center_y,
                visible=i not in hidden_indices,
            ))

        return ResolvedScene(metadata=layout.metadata, elements=result)

    def _detect_all(self, elements: List[LayoutElement]) -> List[Tuple[int, int]]:
        """Return list of (idx, nidx) pairs that overlap."""
        conflicts = []
        pairs_checked = set()
        bucket_size = 80
        buckets: Dict[Tuple[int, int], list] = {}

        visible = [(i, el) for i, el in enumerate(elements) if el.visible]
        if not visible:
            return []

        for idx, el in visible:
            bx = el.px_left // bucket_size, el.px_right // bucket_size
            by = el.px_top // bucket_size, el.px_bottom // bucket_size
            for gx in range(int(bx[0]), int(bx[1]) + 1):
                for gy in range(int(by[0]), int(by[1]) + 1):
                    buckets.setdefault((gx, gy), []).append(idx)

        for idx, el in visible:
            bx = el.px_left // bucket_size, el.px_right // bucket_size
            by = el.px_top // bucket_size, el.px_bottom // bucket_size
            neighbours = set()
            for gx in range(int(bx[0]), int(bx[1]) + 1):
                for gy in range(int(by[0]), int(by[1]) + 1):
                    neighbours.update(buckets.get((gx, gy), []))
            neighbours.discard(idx)

            for nidx in neighbours:
                pair = tuple(sorted((idx, nidx)))
                if pair in pairs_checked:
                    continue
                pairs_checked.add(pair)
                nel = elements[nidx]
                if not nel.visible:
                    continue
                if _rects_overlap(el.bbox_px(), nel.bbox_px()):
                    conflicts.append((idx, nidx))

        return conflicts

    @staticmethod
    def _shift(el: LayoutElement) -> LayoutElement:
        return LayoutElement(
            element=el.element,
            px_top=el.px_top + 22,
            px_bottom=el.px_bottom + 22,
            px_left=el.px_left,
            px_right=el.px_right,
            px_center_x=el.px_center_x,
            px_center_y=el.px_center_y + 22,
        )
