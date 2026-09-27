"""RenderService — unified interface for all chart rendering.

Any component (Telegram, Dashboard, CLI) calls this service.
It never deals with Scenes, Layouts, or Builders directly.
"""

from __future__ import annotations
import io
import logging
from typing import Any, Dict, List, Optional, Union

from PIL import Image

from renderer_v2 import render_snapshot
from renderer_v2.scene import Scene
from renderer_v2.layout import layout_scene, PixelBounds
from renderer_v2.backends.pil import PILBackend
from renderer_v2.theme import Theme, DARK_THEME, LIGHT_THEME

from core_engine.detection.setup_detector import SetupCandidate
from core_engine.simulation.result import TradeResult
from core_engine.simulation.planner import TradePlan
from core_engine.execution.broker import PositionInfo
from core_engine.simulation.lifecycle import TradeLifecycle

from .setup_mapper import setup_to_snapshot
from .trade_mapper import trade_to_snapshot
from .position_mapper import position_to_snapshot

logger = logging.getLogger(__name__)


class RenderService:
    """Single entry point for all chart rendering.

    Methods return PIL Images ready for sending (Telegram, Dashboard, file).

    Usage:
        rs = RenderService(width=1200, height=600, theme="dark")
        img = rs.render_setup(candidate)
        img.save("chart.png")
    """

    def __init__(
        self,
        width: int = 1200,
        height: int = 600,
        theme: str = "light",
    ):
        self.width = width
        self.height = height
        self._theme_name = "light" if theme != "dark" else "dark"
        self._theme = DARK_THEME if self._theme_name == "dark" else LIGHT_THEME
        self._backend = PILBackend(self._theme)

    # ── Public API ──────────────────────────────────────────────

    def render_setup(
        self,
        candidate: SetupCandidate,
        output_path: Optional[str] = None,
        minimal: bool = False,
    ) -> Image.Image:
        """Render a detection setup chart.

        Shows the chart with BOS, CHoCH, MSS, OB, FVG, liquidity,
        entry, SL, TP levels.

        Args:
            candidate: detected setup
            output_path: optional save path
            minimal: if True, render only candles + Entry/SL/TP (no overlays)

        Returns:
            PIL Image
        """
        snapshot = setup_to_snapshot(candidate)
        return self._render_snapshot(snapshot, output_path, minimal=minimal)

    def render_trade(
        self,
        result: TradeResult,
        candles: List[Dict],
        plan: Optional[TradePlan] = None,
        symbol: str = "",
        timeframe: str = "",
        output_path: Optional[str] = None,
        minimal: bool = False,
    ) -> Image.Image:
        """Render a completed trade result chart.

        Shows entry, SL, TPs, BE, trailing, exit, and R multiple.

        Args:
            result: trade result with events
            candles: OHLC data
            plan: trade plan (optional)
            symbol: symbol name
            timeframe: timeframe label
            output_path: optional save path
            minimal: if True, render only candles + Entry/SL/TP (no overlays)

        Returns:
            PIL Image
        """
        snapshot = trade_to_snapshot(result, candles, plan, symbol, timeframe)
        return self._render_snapshot(snapshot, output_path, minimal=minimal)

    def render_position(
        self,
        position: PositionInfo,
        lifecycle: Optional[TradeLifecycle] = None,
        candles: Optional[List[Dict]] = None,
        current_price: Optional[float] = None,
        symbol: str = "",
        timeframe: str = "",
        total_r: float = 0.0,
        output_path: Optional[str] = None,
        minimal: bool = False,
    ) -> Image.Image:
        """Render an active open position chart.

        Args:
            position: broker position info
            lifecycle: optional lifecycle for state (BE/trailing)
            candles: optional OHLC data
            current_price: current market price
            symbol: symbol name
            timeframe: timeframe label
            total_r: current R multiple
            output_path: optional save path
            minimal: if True, render only candles + Entry/SL/TP (no overlays)

        Returns:
            PIL Image
        """
        snapshot = position_to_snapshot(
            position, lifecycle, candles, current_price,
            symbol, timeframe, total_r,
        )
        return self._render_snapshot(snapshot, output_path, minimal=minimal)

    def render_snapshot(
        self,
        snapshot: Dict[str, Any],
        output_path: Optional[str] = None,
        minimal: bool = False,
    ) -> Image.Image:
        """Render a pre-built snapshot dict directly.

        Args:
            snapshot: canonical snapshot dict
            output_path: optional save path
            minimal: if True, render only candles + Entry/SL/TP (no overlays)

        Returns:
            PIL Image
        """
        return self._render_snapshot(snapshot, output_path, minimal=minimal)

    def render_scene(
        self,
        scene: Scene,
        output_path: Optional[str] = None,
    ) -> Image.Image:
        """Render an arbitrary Scene directly.

        For advanced use cases where the caller built a custom Scene.
        """
        return self._render_scene(scene, output_path)

    def to_bytes(self, image: Image.Image, fmt: str = "PNG") -> bytes:
        """Convert a PIL Image to bytes (for Telegram send_photo)."""
        buf = io.BytesIO()
        image.save(buf, format=fmt)
        return buf.getvalue()

    # ── Theme switching ─────────────────────────────────────────

    @property
    def theme(self) -> str:
        return self._theme_name

    def set_theme(self, theme: str):
        """Switch theme ('dark' or 'light')."""
        self._theme_name = "light" if theme != "dark" else "dark"
        self._theme = DARK_THEME if self._theme_name == "dark" else LIGHT_THEME
        self._backend = PILBackend(self._theme)

    # ── Internal ────────────────────────────────────────────────

    def _render_snapshot(self, snapshot: Dict[str, Any],
                         output_path: Optional[str] = None,
                         minimal: bool = False) -> Image.Image:
        """Render a snapshot dict through the full pipeline."""
        return render_snapshot(
            snapshot,
            output_path=output_path,
            theme=self._theme,
            width=self.width,
            height=self.height,
            minimal=minimal,
        )

    def _render_scene(self, scene: Scene,
                      output_path: Optional[str] = None) -> Image.Image:
        """Render a pre-built Scene through layout + backend."""
        px = PixelBounds(
            top=0, bottom=self.height, left=0, right=self.width,
            width=self.width, height=self.height,
        )
        layout = layout_scene(scene, px, self._theme)
        return self._backend.render(layout, output_path)


# Module-level convenience instance
render_service = RenderService()
