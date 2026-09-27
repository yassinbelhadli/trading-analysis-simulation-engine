"""RendererBackend — abstract base for all rendering backends."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional

from ..layout import LayoutScene
from ..collision import ResolvedScene, CollisionResolver
from ..theme import Theme


class RendererBackend(ABC):
    """Plug-in interface for rendering backends.

    Subclasses implement render() which produces backend-specific output
    (PIL Image, matplotlib figure, SVG string, etc.)
    """

    def __init__(self, theme: Optional[Theme] = None):
        self.theme = theme or Theme()
        self.resolver = CollisionResolver()

    def prepare(self, layout: LayoutScene) -> ResolvedScene:
        """Run collision resolution before rendering."""
        return self.resolver.resolve(layout)

    @abstractmethod
    def render(self, layout: LayoutScene, output_path: Optional[str] = None):
        """Render the layout scene into backend-specific output.

        Args:
            layout: The laid-out scene with pixel coordinates.
            output_path: Optional file path to save the output.

        Returns:
            Backend-specific result (PIL Image, matplotlib Figure, SVG string, etc.)
        """
