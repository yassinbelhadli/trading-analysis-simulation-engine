"""Theme registry — central color, font, pen, brush, and layout config."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional


# ── Color ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Color:
    hex: str

    def rgba(self, alpha: float = 1.0) -> tuple:
        h = self.hex.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (r, g, b, int(255 * alpha))


# ── Font ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Font:
    family: str = "Segoe UI"
    size: int = 12
    bold: bool = False
    italic: bool = False
    fallbacks: tuple = ("Arial", "DejaVu Sans", "sans-serif")


# ── Pen ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Pen:
    color: Color
    width: float = 1.5
    style: str = "solid"  # solid, dashed, dotted
    dash_pattern: tuple = ()


# ── Brush ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Brush:
    fill: Color
    alpha: float = 0.3
    border: Optional[Pen] = None


# ── Theme ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Theme:
    """Complete styling config for a renderer."""

    # ── Core palette ──
    background: Color = Color("#0d1117")
    surface: Color = Color("#161b22")
    border: Color = Color("#30363d")
    text_primary: Color = Color("#e6edf3")
    text_secondary: Color = Color("#8b949e")
    text_muted: Color = Color("#484f58")
    grid_lines: Color = Color("#21262d")

    # ── Directional ──
    bull: Color = Color("#22c55e")
    bear: Color = Color("#ef4444")
    neutral: Color = Color("#8b949e")

    # ── ICT concepts ──
    ob_bull: Color = Color("#60a5fa")
    ob_bear: Color = Color("#60a5fa")
    fvg_bull: Color = Color("#a78bfa")
    fvg_bear: Color = Color("#a78bfa")
    structure_bos: Color = Color("#3b82f6")
    structure_choch: Color = Color("#eab308")
    structure_mss: Color = Color("#a855f7")
    liquidity: Color = Color("#f97316")
    swing: Color = Color("#e2e8f0")
    trade_entry: Color = Color("#22c55e")
    trade_sl: Color = Color("#ef4444")
    trade_tp: Color = Color("#10b981")
    trade_exit: Color = Color("#fbbf24")
    trade_partial: Color = Color("#a78bfa")
    trade_be: Color = Color("#e2e8f0")
    current_price: Color = Color("#2962ff")
    premium: Color = Color("#ef4444")     # sell-side
    discount: Color = Color("#22c55e")    # buy-side
    session_asia: Color = Color("#6366f1")
    session_london: Color = Color("#f59e0b")
    session_ny: Color = Color("#ef4444")

    # ── Fonts ──
    chart_font: Font = Font(size=9)
    label_font: Font = Font(size=10)
    title_font: Font = Font(size=14, bold=True)
    badge_font: Font = Font(size=9, bold=True)
    axis_font: Font = Font(size=10)

    # ── Pens ──
    def pen(self, color_key: str, width: float = 1.5, style: str = "solid") -> Pen:
        c = getattr(self, color_key, self.text_primary)
        return Pen(color=c, width=width, style=style)

    def dashed(self, color_key: str, width: float = 1.0) -> Pen:
        c = getattr(self, color_key, self.text_primary)
        return Pen(color=c, width=width, style="dashed", dash_pattern=(6, 3))

    def dotted(self, color_key: str, width: float = 1.0) -> Pen:
        c = getattr(self, color_key, self.text_primary)
        return Pen(color=c, width=width, style="dotted", dash_pattern=(2, 2))

    # ── Brushes ──
    def brush(self, color_key: str, alpha: float = 0.3) -> Brush:
        c = getattr(self, color_key, self.text_primary)
        return Brush(fill=c, alpha=alpha)

    # ── Layout ──
    chart_margin: int = 8
    label_padding: tuple = (4, 8)    # (vertical, horizontal)
    badge_radius: int = 4
    corner_radius: int = 6
    line_label_offset: int = 4       # px between line and its label
    arrow_size: int = 6

    # ── Sizes ──
    candle_width_ratio: float = 0.7  # candle body width relative to total slot
    chart_width: int = 1200
    chart_height: int = 600
    header_height: int = 40
    footer_height: int = 30


# ── Presets ──────────────────────────────────────────────────────
DARK_THEME = Theme(
    grid_lines=Color("#30363d"),
    chart_font=Font(size=9),
    label_font=Font(size=10),
    title_font=Font(size=14, bold=True),
    badge_font=Font(size=9, bold=True),
    axis_font=Font(size=10),
)

LIGHT_THEME = Theme(
    background=Color("#ffffff"),
    surface=Color("#ffffff"),
    border=Color("#e5e7eb"),
    text_primary=Color("#131722"),
    text_secondary=Color("#5d606b"),
    text_muted=Color("#9aa0a6"),
    grid_lines=Color("#eef0f2"),
    bull=Color("#2962ff"),
    bear=Color("#1a1a1a"),
    ob_bull=Color("#42a5f5"),
    ob_bear=Color("#42a5f5"),
    fvg_bull=Color("#ce93d8"),
    fvg_bear=Color("#ce93d8"),
    structure_bos=Color("#1e88e5"),
    structure_choch=Color("#fbc02d"),
    structure_mss=Color("#7b1fa2"),
    liquidity=Color("#fb8c00"),
    swing=Color("#9e9e9e"),
    trade_entry=Color("#2962ff"),
    trade_sl=Color("#ef5350"),
    trade_tp=Color("#089981"),
    trade_exit=Color("#fbc02d"),
    trade_partial=Color("#ce93d8"),
    trade_be=Color("#9e9e9e"),
    current_price=Color("#2962ff"),
    premium=Color("#ef5350"),
    discount=Color("#2196f3"),
    chart_font=Font(size=10),
    label_font=Font(size=11),
    axis_font=Font(size=11),
    badge_font=Font(size=9, bold=True),
)
