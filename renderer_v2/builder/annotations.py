"""AnnotationBuilder — adds informational labels from snapshot + explainability data."""

from typing import Dict, List, Any

from ..scene import (
    Element, LayerType, ElementType, BoundingBox, Direction,
    CollisionPolicy,
)


class AnnotationBuilder:

    def build(self, snapshot: Dict[str, Any]) -> List[Element]:
        return []
