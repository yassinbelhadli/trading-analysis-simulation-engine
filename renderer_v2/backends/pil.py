"""PIL rendering backend — draws scene elements onto a Pillow Image.

This backend is the primary production renderer. It produces
full chart snapshots with ICT overlays for Telegram / Dashboard.

Design (TradingView-like):
    ┌──────────────────────────────────────────┐
    │ Header (symbol · timeframe)               │
    ├──────────────────────────────────────────┤
    │  InfoCard   Candles + ICT overlays   │px│  <- right price axis
    │  (score)                                │  │
    ├──────────────────────────────────────────┤
    │ Time axis                                  │
    └──────────────────────────────────────────┘
"""

from __future__ import annotations
import math
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from ..layout import LayoutScene, LayoutElement
import os
from ..theme import Theme, Color, Font, Pen, Brush
from ..enums import (
    ElementType, LayerType, TradeKind, Direction, LiquidityKind,
)
from .base import RendererBackend

logger = logging.getLogger(__name__)

# ── Layout geometry (pixels) ─────────────────────────────────────
HEADER_H = 34
LEFT_MARGIN = 6
PRICE_AXIS_W = 78
TIME_AXIS_H = 26


@dataclass
class _FontCache:
    regular: Dict[int, ImageFont.FreeTypeFont] = None
    bold: Dict[int, ImageFont.FreeTypeFont] = None

    def __post_init__(self):
        self.regular = {}
        self.bold = {}


class _LabelStack:
    """Places right-edge level labels with vertical de-collision nudging.

    Anchors are sorted by price so that stacked labels read top-down. Each
    placed box is recorded into ``record`` (when provided) as
    ``(top, bottom, right, left)`` for post-render QA overlap checks.
    """

    def __init__(self, min_gap: int = 13, record: Optional[list] = None):
        self.min_gap = min_gap
        self.placed: List[Tuple[float, float]] = []
        self._record = record

    def place(self, draw: ImageDraw, right_x: float, y: float,
              text: str, color: tuple, font: ImageFont.FreeTypeFont,
              top_clip: float, bot_clip: float) -> None:
        if not text:
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        cy = self._nudge(y, th, top_clip, bot_clip)
        cy = max(top_clip + th / 2, min(bot_clip - th / 2, cy))
        top, bot = cy - th / 2, cy + th / 2
        draw.text((right_x - tw, cy - th / 2), text, fill=color, font=font)
        self.placed.append((top, bot))
        if self._record is not None:
            self._record.append((top, bot, right_x, right_x - tw))

    def _nudge(self, y: float, th: float, top_clip: float, bot_clip: float) -> float:
        lo, hi = top_clip + th / 2, bot_clip - th / 2
        if lo > hi:
            return lo
        y = max(lo, min(hi, y))
        for step in range(1, 40):
            for cy in (y - step * self.min_gap, y + step * self.min_gap):
                cy = max(lo, min(hi, cy))
                top, bot = cy - th / 2, cy + th / 2
                clash = any(not (bot <= pt or top >= pb) for pt, pb in self.placed)
                if not clash:
                    return cy
        return y


class PILBackend(RendererBackend):

    def __init__(self, theme=None):
        super().__init__(theme)
        self._font_cache = _FontCache()
        self._labels: Optional[_LabelStack] = None
        self._drawn_labels: List[Tuple[float, float, float, float]] = []

    @property
    def drawn_labels(self) -> List[Tuple[float, float, float, float]]:
        """(top, bottom, right, left) boxes of every right-edge level label
        drawn in the most recent render — used by the QA harness to verify
        there is no label overlap or clipping."""
        return list(self._drawn_labels)

    # ── Fonts ────────────────────────────────────────────────────
    def _get_font(self, font: Font) -> ImageFont.FreeTypeFont:
        cache = self._font_cache.bold if font.bold else self._font_cache.regular
        if font.size in cache:
            return cache[font.size]
        path = _find_font_path(font.family)
        if path:
            try:
                f = ImageFont.truetype(path, font.size)
                cache[font.size] = f
                return f
            except (OSError, IOError):
                pass
        for fallback in font.fallbacks:
            path = _find_font_path(fallback)
            if path:
                try:
                    f = ImageFont.truetype(path, font.size)
                    cache[font.size] = f
                    return f
                except (OSError, IOError):
                    pass
        f = ImageFont.load_default()
        cache[font.size] = f
        return f

    def _theme_color(self, color: Color) -> tuple:
        return color.rgba(1.0)[:3]

    def _theme_rgba(self, color: Color, alpha: float) -> tuple:
        return color.rgba(alpha)

    def _x(self, x: float) -> float:
        return x + LEFT_MARGIN

    def _y(self, y: float) -> float:
        return y + HEADER_H

    # ── Main render ──────────────────────────────────────────────
    def render(self, layout: LayoutScene, output_path: Optional[str] = None):
        resolved = self.prepare(layout)

        chart_w = int(layout.mapper.bounds.width)
        chart_h = int(layout.mapper.bounds.height)
        w = LEFT_MARGIN + chart_w + PRICE_AXIS_W
        h = HEADER_H + chart_h + TIME_AXIS_H

        img = Image.new("RGBA", (w, h), self._theme_color(self.theme.background))
        draw = ImageDraw.Draw(img)

        chart_l = LEFT_MARGIN
        chart_t = HEADER_H
        chart_r = chart_l + chart_w
        chart_b = chart_t + chart_h

        # Header bar
        self._draw_header(draw, layout, w)

        # Chart surface
        draw.rectangle(
            [chart_l, chart_t, chart_r - 1, chart_b - 1],
            fill=self._theme_color(self.theme.surface),
            outline=self._theme_color(self.theme.border),
        )

        self._labels = _LabelStack(record=self._drawn_labels)
        self._drawn_labels.clear()

        minimal = bool(layout.metadata.get("_minimal"))
        if not minimal:
            self._draw_premium_discount_zones(draw, layout, chart_l, chart_t, chart_r, chart_b)
        self._draw_grid_and_price_axis(draw, layout, chart_l, chart_t, chart_r, chart_b)

        layer_order = [
            LayerType.CANDLES, LayerType.ORDER_BLOCK, LayerType.FVG,
            LayerType.STRUCTURE, LayerType.LIQUIDITY, LayerType.SWINGS,
            LayerType.TRADES, LayerType.LABELS, LayerType.OVERLAY,
        ]
        for lt in layer_order:
            layer_els = [e for e in resolved.elements if e.element.layer == lt]
            for el in layer_els:
                if not el.visible:
                    continue
                self._draw_element(draw, el, layout)

        if not minimal:
            self._draw_current_price(draw, layout, chart_l, chart_t, chart_r, chart_b)
            self._draw_trade_events(draw, layout, chart_l, chart_t, chart_r, chart_b)
        self._draw_time_axis(draw, layout, chart_l, chart_b, chart_r)

        # Flatten RGBA (semi-transparent fills) over the background color so
        # the saved PNG is opaque and the tints look correct.
        bg = self._theme_color(self.theme.background) + (255,)
        img = Image.alpha_composite(Image.new("RGBA", img.size, bg), img).convert("RGB")

        if output_path:
            img.save(output_path, "PNG")
            logger.info("Rendered scene to %s", output_path)

        return img

    # ── Header ───────────────────────────────────────────────────
    def _draw_header(self, draw: ImageDraw, layout: LayoutScene, width: int):
        metadata = layout.metadata
        symbol = metadata.get("symbol", "")
        tf = metadata.get("timeframe", "")
        scoring = metadata.get("scoring", {}) or {}
        drawing = metadata.get("drawing", {}) or {}
        direction = scoring.get("direction") or drawing.get("buy_sell", "")
        session = (metadata.get("session_label")
                   or (metadata.get("session", {}) or {}).get("label")
                   or metadata.get("original", {}).get("session_label")
                   or "")

        title_font = self._get_font(self.theme.title_font)
        text_color = self._theme_color(self.theme.text_primary)

        # Left: "BUY XAUUSD | M5 | London"
        parts = [p for p in (direction, symbol, tf, session) if p]
        left = " | ".join(parts)
        draw.text((LEFT_MARGIN + 8, HEADER_H // 2 - 9), left,
                  fill=text_color, font=title_font)

        # Right: "Score 96   Conf 88"
        right_parts = []
        if scoring.get("score") is not None:
            right_parts.append(f"Score {scoring['score']:.0f}")
        if scoring.get("confidence_score") is not None:
            right_parts.append(f"Conf {scoring['confidence_score']:.0f}%")
        if right_parts:
            axis_font = self._get_font(self.theme.axis_font)
            muted = self._theme_color(self.theme.text_muted)
            text = "    ".join(right_parts)
            tw = self._text_w(draw, text, axis_font)
            draw.text((width - tw - 12, HEADER_H // 2 - 7), text,
                      fill=muted, font=axis_font)

        draw.line([(0, HEADER_H - 1), (width, HEADER_H - 1)],
                  fill=self._theme_color(self.theme.border), width=1)

    # ── Premium / Discount zones ─────────────────────────────────
    def _draw_premium_discount_zones(self, draw, layout, chart_l, chart_t, chart_r, chart_b):
        pd = layout.metadata.get("premium_discount", {})
        if not pd or "equilibrium" not in pd:
            return
        eq = pd["equilibrium"]
        premium_high = pd.get("premium_high")
        discount_low = pd.get("discount_low")
        if premium_high is None or discount_low is None:
            return

        mapper = layout.mapper
        y_eq = self._y(mapper.y_of(eq))
        y_prem = self._y(mapper.y_of(premium_high))
        y_disc = self._y(mapper.y_of(discount_low))

        if y_prem < y_eq:
            draw.rectangle(
                [chart_l, y_prem, chart_r, y_eq],
                fill=self._theme_rgba(self.theme.premium, 0.06),
            )
        if y_disc > y_eq:
            draw.rectangle(
                [chart_l, y_eq, chart_r, y_disc],
                fill=self._theme_rgba(self.theme.discount, 0.06),
            )
        draw.line([(chart_l, y_eq), (chart_r, y_eq)],
                  fill=self._theme_color(self.theme.text_muted), width=1)

    # ── Grid + price axis ────────────────────────────────────────
    def _draw_grid_and_price_axis(self, draw, layout, chart_l, chart_t, chart_r, chart_b):
        mapper = layout.mapper
        price_min = mapper.viewport.price_min
        price_max = mapper.viewport.price_max
        price_range = mapper.viewport.price_range

        grid_color = self._theme_color(self.theme.grid_lines)
        text_color = self._theme_color(self.theme.text_muted)
        font = self._get_font(self.theme.axis_font)

        step = self._nice_step(price_range / 5)
        if step <= 0:
            step = price_range / 5

        start_price = _round_down(price_min, step)
        px = start_price
        last_label_y = None
        while px <= price_max:
            y_pos = self._y(mapper.y_of(px))
            if chart_t + 4 <= y_pos <= chart_b - 4:
                draw.line([(chart_l, y_pos), (chart_r, y_pos)],
                          fill=grid_color, width=1)
                label = _format_price(px, step)
                bbox = draw.textbbox((0, 0), label, font=font)
                th = bbox[3] - bbox[1]
                # Skip labels too close to the previous one to avoid overlap.
                if last_label_y is None or (last_label_y - (y_pos - th)) >= 14:
                    draw.text((chart_r + 8, y_pos - th / 2), label,
                              fill=text_color, font=font)
                    last_label_y = y_pos
            px += step

    # ── Current price line + pill ────────────────────────────────
    def _draw_current_price(self, draw, layout, chart_l, chart_t, chart_r, chart_b):
        current_price = layout.metadata.get("current_price")
        if current_price is None:
            return
        mapper = layout.mapper
        y = self._y(mapper.y_of(current_price))
        if y < chart_t or y > chart_b:
            return

        color = self._theme_color(self.theme.current_price)
        self._draw_dashed_line(draw, chart_l, y, chart_r, y, color,
                               width=1, dash_len=5, gap_len=4)

        label = _format_price(current_price, 0.01)
        font = self._get_font(self.theme.badge_font)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pill_w = tw + 10
        pill_h = th + 6
        image_w = chart_r + PRICE_AXIS_W
        x2 = min(chart_r + 4 + pill_w, image_w - 4)
        x1 = x2 - pill_w
        y1 = y - pill_h / 2
        y2 = y + pill_h / 2
        self._draw_pill(draw, x1, y1, x2, y2, fill=color,
                        text=label, text_color=(255, 255, 255), font=font)

    # ── Time axis ────────────────────────────────────────────────
    def _draw_time_axis(self, draw, layout, chart_l, chart_b, chart_r):
        mapper = layout.mapper
        ohlc = layout.metadata.get("chart", {}).get("ohlc", [])
        if not ohlc:
            return

        font = self._get_font(self.theme.axis_font)
        text_color = self._theme_color(self.theme.text_secondary)
        candle_count = len(ohlc)

        label_count = min(6, candle_count)
        step = max(1, candle_count // label_count)

        last_x = None
        for i in range(0, candle_count, step):
            x_pos = self._x(mapper.x_of(i))
            candle = ohlc[i]
            time_str = _format_time(candle.get("time", ""))
            if not time_str:
                continue
            bbox = draw.textbbox((0, 0), time_str, font=font)
            tw = bbox[2] - bbox[0]
            # Skip labels that would overlap the previous one.
            if last_x is not None and (x_pos - tw / 2) < (last_x + 6):
                continue
            tx = x_pos - tw / 2
            if tx < chart_l:
                tx = chart_l
            if tx + tw > chart_r:
                tx = chart_r - tw
            draw.text((tx, chart_b + 6), time_str, fill=text_color, font=font)
            last_x = tx + tw

        draw.line([(chart_l, chart_b), (chart_r, chart_b)],
                  fill=self._theme_color(self.theme.border), width=1)

    def _nice_step(self, raw: float) -> float:
        if raw <= 0:
            return 1
        magnitude = 10 ** int(math.log10(raw))
        residual = raw / magnitude
        for nice in [1, 2, 2.5, 5, 10]:
            if residual <= nice:
                return nice * magnitude
        return magnitude * 10

    # ── Element dispatch ─────────────────────────────────────────
    def _draw_element(self, draw: ImageDraw, el: LayoutElement,
                      layout: LayoutScene):
        et = el.element.element_type
        try:
            if et == ElementType.CANDLE:
                self._draw_candle(draw, el, layout)
            elif et == ElementType.ORDER_BLOCK:
                self._draw_ob(draw, el, layout)
            elif et == ElementType.FVG:
                self._draw_fvg(draw, el, layout)
            elif et == ElementType.STRUCTURE:
                self._draw_structure(draw, el, layout)
            elif et == ElementType.LIQUIDITY:
                self._draw_liquidity(draw, el, layout)
            elif et == ElementType.SWING:
                self._draw_swing(draw, el, layout)
            elif et == ElementType.TRADE:
                self._draw_trade(draw, el, layout)
            elif et == ElementType.LABEL:
                self._draw_annotation(draw, el, layout)
        except Exception as e:
            logger.debug("Skipping element %s: %s", et.name, e)

    # ── Draw helpers ─────────────────────────────────────────────
    def _text_w(self, draw: ImageDraw, text: str, font) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def _draw_pill(self, draw, x1, y1, x2, y2, fill, text, text_color, font):
        draw.rounded_rectangle([x1, y1, x2, y2], radius=(y2 - y1) / 2,
                               fill=fill)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        cx = (x1 + x2) / 2 - tw / 2
        cy = (y1 + y2) / 2 - th / 2
        draw.text((cx, cy), text, fill=text_color, font=font)

    def _draw_candle(self, draw: ImageDraw, el: LayoutElement, layout: LayoutScene):
        data = el.element.data
        o, c_val = data.get("open", 0), data.get("close", 0)
        high, low = data.get("high", 0), data.get("low", 0)

        x = self._x(el.px_center_x)
        y_top = self._y(layout.mapper.y_of(high))
        y_bot = self._y(layout.mapper.y_of(low))
        y_o = self._y(layout.mapper.y_of(o))
        y_c = self._y(layout.mapper.y_of(c_val))

        color = self.theme.bull if c_val >= o else self.theme.bear
        fill_color = self._theme_color(color)

        slot = layout.mapper.bounds.width / max(1, layout.mapper.viewport.candle_count)
        half_width = max(1.5, slot * 0.35)

        draw.line([(x, y_top), (x, y_bot)], fill=fill_color, width=1)
        draw.rectangle(
            [x - half_width, min(y_o, y_c),
             x + half_width, max(y_o, y_c)],
            fill=fill_color,
            outline=fill_color,
            width=1,
        )

    def _draw_ob(self, draw: ImageDraw, el: LayoutElement, layout: LayoutScene):
        color = self.theme.ob_bull if el.element.direction == Direction.BULLISH else self.theme.ob_bear
        x1 = self._x(el.px_left)
        x2 = self._x(el.px_right)
        chart_r = LEFT_MARGIN + layout.mapper.bounds.width
        y1 = self._y(el.px_top)
        y2 = self._y(el.px_bottom)
        if y2 - y1 < 2:
            return
        c = self._theme_color(color)
        draw.rectangle([x1, y1, x2, y2], fill=self._theme_rgba(color, 0.16),
                       outline=c, width=1)
        label = el.element.label or "OB"
        font = self._get_font(self.theme.badge_font)
        tw = self._text_w(draw, label, font) + 8
        th = 12
        lx = min(x1, chart_r - tw)
        draw.rounded_rectangle([lx, y1, lx + tw, y1 + th], radius=6,
                               fill=self._theme_rgba(color, 0.85))
        draw.text((lx + 4, y1 + 1), label, fill=(255, 255, 255), font=font)

    def _draw_fvg(self, draw: ImageDraw, el: LayoutElement, layout: LayoutScene):
        color = self.theme.fvg_bull if el.element.direction == Direction.BULLISH else self.theme.fvg_bear
        x1 = self._x(el.px_left)
        x2 = self._x(el.px_right)
        chart_r = LEFT_MARGIN + layout.mapper.bounds.width
        y1 = self._y(el.px_top)
        y2 = self._y(el.px_bottom)
        if y2 - y1 < 2:
            return
        c = self._theme_color(color)
        draw.rectangle([x1, y1, x2, y2], fill=self._theme_rgba(color, 0.10))
        self._draw_dashed_line(draw, x1, y1, x2, y1, c, 1, 4, 3)
        self._draw_dashed_line(draw, x2, y1, x2, y2, c, 1, 4, 3)
        self._draw_dashed_line(draw, x1, y2, x2, y2, c, 1, 4, 3)
        self._draw_dashed_line(draw, x1, y1, x1, y2, c, 1, 4, 3)

        label = el.element.label or "FVG"
        if el.element.data.get("mitigated"):
            return
        font = self._get_font(self.theme.badge_font)
        tw = self._text_w(draw, label, font) + 8
        th = 12
        lx = x1 + (x2 - x1 - tw) / 2
        ly = y1 + (y2 - y1 - th) / 2
        lx = max(x1, min(x2 - tw, lx))
        ly = max(y1, min(y2 - th, ly))
        draw.rounded_rectangle([lx, ly, lx + tw, ly + th], radius=6,
                               fill=self._theme_rgba(color, 0.85))
        draw.text((lx + 4, ly + 1), label, fill=(255, 255, 255), font=font)

    def _draw_structure(self, draw: ImageDraw, el: LayoutElement, layout: LayoutScene):
        kind = el.element.kind
        kind_name = kind.name if kind else ""
        if kind_name == "BOS":
            color = self.theme.structure_bos
        elif kind_name == "CHOCH":
            color = self.theme.structure_choch
        else:
            color = self.theme.structure_mss

        c = self._theme_color(color)
        y = self._y(el.px_center_y)
        chart_l = LEFT_MARGIN
        chart_r = layout.mapper.bounds.width + LEFT_MARGIN
        x_start = self._x(el.px_left)

        draw.line([(x_start, y), (chart_r, y)], fill=c, width=1)

        if self._labels:
            font = self._get_font(self.theme.label_font)
            self._labels.place(draw, chart_r - 8, y,
                               el.element.label or kind_name, c, font,
                               HEADER_H + 6, HEADER_H + layout.mapper.bounds.height - 6)

    def _draw_liquidity(self, draw: ImageDraw, el: LayoutElement, layout: LayoutScene):
        color = self.theme.liquidity
        c = self._theme_color(color)
        y = self._y(el.px_center_y)
        chart_l = LEFT_MARGIN
        chart_r = layout.mapper.bounds.width + LEFT_MARGIN

        kind = el.element.kind
        if kind == LiquidityKind.SWEEP:
            self._draw_dashed_line(draw, chart_l, y, chart_r, y, c, width=1,
                                   dash_len=3, gap_len=4)
            label = "Sweep"
        else:
            self._draw_dashed_line(draw, chart_l, y, chart_r, y, c, width=1)
            label = el.element.label or "PDH"

        if self._labels:
            font = self._get_font(self.theme.label_font)
            self._labels.place(draw, chart_r - 8, y, label, c, font,
                               HEADER_H + 6, HEADER_H + layout.mapper.bounds.height - 6)

    def _draw_swing(self, draw: ImageDraw, el: LayoutElement, layout: LayoutScene):
        color = self.theme.swing
        x = self._x(el.px_center_x)
        y = self._y(el.px_center_y)
        r = 3
        draw.ellipse([x - r, y - r, x + r, y + r], fill=self._theme_color(color))

    def _draw_trade(self, draw: ImageDraw, el: LayoutElement, layout: LayoutScene):
        kind = el.element.kind
        kind_name = kind.name if kind else ""
        chart_l = LEFT_MARGIN
        chart_r = layout.mapper.bounds.width + LEFT_MARGIN

        if kind_name == "ENTRY":
            color = self.theme.trade_entry
            width, style = 2, "solid"
        elif kind_name == "STOP_LOSS":
            color = self.theme.trade_sl
            width, style = 2, "solid"
        elif kind_name == "TAKE_PROFIT":
            color = self.theme.trade_tp
            width, style = 1, "dashed"
        else:
            color = self.theme.trade_exit
            width, style = 1, "dashed"

        c = self._theme_color(color)
        y = self._y(el.px_center_y)

        if style == "dashed":
            self._draw_dashed_line(draw, chart_l, y, chart_r, y, c, width=width,
                                   dash_len=6, gap_len=4)
        else:
            draw.line([(chart_l, y), (chart_r, y)], fill=c, width=width)

        if self._labels:
            font = self._get_font(self.theme.label_font)
            self._labels.place(draw, chart_r - 8, y,
                               el.element.label or kind_name, c, font,
                               HEADER_H + 6, HEADER_H + layout.mapper.bounds.height - 6)

    def _draw_annotation(self, draw: ImageDraw, el: LayoutElement, layout: LayoutScene):
        text = el.element.label
        if not text:
            return
        font = self._get_font(self.theme.label_font)
        color = self._theme_color(self.theme.text_secondary)
        x = self._x(el.px_left)
        y = self._y(el.px_center_y)
        draw.text((x, y), text, fill=color, font=font)

    # ── Info card ────────────────────────────────────────────────
    def _draw_info_card(self, draw, layout, chart_l, chart_t, chart_r, chart_b):
        scoring = layout.metadata.get("scoring", {}) or {}
        drawing = layout.metadata.get("drawing", {}) or {}
        trade = layout.metadata.get("trade", {}) or {}
        meta = layout.metadata

        direction = scoring.get("direction") or drawing.get("buy_sell") or trade.get("direction") or ""
        score = scoring.get("score")
        confidence = scoring.get("confidence_score")
        reasons = scoring.get("reasons", []) or []

        entry = _first_val(drawing, "entry_price") or _first_val(trade, "entry_price")
        sl = _first_val(drawing, "sl_price") or _first_val(trade, "sl_price")
        tp_prices = drawing.get("tp") or trade.get("tp_prices") or []
        if not isinstance(tp_prices, list):
            tp_prices = [tp_prices] if tp_prices else []

        if not direction and entry is None and sl is None and not tp_prices and score is None:
            return

        symbol = meta.get("symbol", "")
        timeframe = meta.get("timeframe", "")

        # ── content ──
        rows: List[Tuple[str, str, tuple]] = []
        font_title = self._get_font(Font(size=17, bold=True))
        font_label = self._get_font(Font(size=12, bold=True))
        font_value = self._get_font(Font(size=12))
        font_small = self._get_font(Font(size=11))

        sell_color = self._theme_color(self.theme.trade_sl)
        buy_color = self._theme_color(self.theme.trade_tp)
        label_color = self._theme_color(self.theme.text_secondary)
        value_color = self._theme_color(self.theme.text_primary)
        muted = self._theme_color(self.theme.text_muted)

        dir_text = direction or "—"
        dir_color = sell_color if direction == "SELL" else buy_color
        head = f"{dir_text} {symbol} {timeframe}".strip()
        head_w = self._text_w(draw, head, font_title)
        card_w = head_w + 40

        score_line = ""
        if score is not None:
            score_line = f"Score {score:.0f}"
            if confidence is not None:
                score_line += f"   Conf {confidence:.0f}%"
            card_w = max(card_w, self._text_w(draw, score_line, font_label) + 40)

        levels: List[Tuple[str, Optional[float]]] = [("Entry", entry), ("SL", sl)]
        for i, tp in enumerate(tp_prices):
            try:
                levels.append((f"TP{i+1}", float(tp)))
            except (ValueError, TypeError):
                continue
        rr = _calc_rr(entry, sl, tp_prices)

        for name, val in levels:
            if val is None:
                continue
            line = f"{name:<6}{val:,.2f}"
            card_w = max(card_w, self._text_w(draw, line, font_value) + 40)

        rr_line = ""
        if rr is not None:
            rr_line = f"RR   1:{rr:.1f}"
            card_w = max(card_w, self._text_w(draw, rr_line, font_value) + 40)

        # card geometry
        card_w = min(card_w, 300)
        pad = 10
        line_h = 19
        title_h = 24

        checklist = [r for r in reasons if r][:8]
        n_rows = 0
        if levels:
            n_rows += sum(1 for _, v in levels if v is not None)
        if rr_line:
            n_rows += 1
        if checklist:
            n_rows += (len(checklist) + 1) // 2
        body_h = max(0, n_rows) * line_h + (18 if checklist else 6)
        card_h = pad + title_h + 6 + body_h + pad

        x1 = chart_l + 10
        y1 = chart_t + 10
        x2 = x1 + card_w
        y2 = y1 + card_h
        if x2 > chart_r - 10 or y2 > chart_b - 10:
            return

        bg = (255, 255, 255, 242) if self._theme_color(self.theme.background) == (255, 255, 255) \
            else self._theme_rgba(self.theme.surface, 0.92)
        draw.rounded_rectangle([x1, y1, x2, y2], radius=8,
                               fill=bg, outline=self._theme_color(self.theme.border), width=1)

        cy = y1 + pad
        draw.text((x1 + pad, cy), head, fill=dir_color, font=font_title)
        cy += title_h
        if score_line:
            draw.text((x1 + pad, cy), score_line, fill=muted, font=font_label)
            cy += line_h

        if levels:
            draw.line([(x1 + pad, cy - 3), (x2 - pad, cy - 3)],
                      fill=self._theme_color(self.theme.border), width=1)
            for name, val in levels:
                if val is None:
                    continue
                draw.text((x1 + pad, cy), name, fill=label_color, font=font_label)
                draw.text((x1 + pad + 52, cy), f"{val:,.2f}", fill=value_color, font=font_value)
                cy += line_h
        if rr_line:
            draw.text((x1 + pad, cy), "RR", fill=label_color, font=font_label)
            draw.text((x1 + pad + 52, cy), f"1:{rr:.1f}", fill=value_color, font=font_value)
            cy += line_h

        if checklist:
            draw.line([(x1 + pad, cy - 3), (x2 - pad, cy - 3)],
                      fill=self._theme_color(self.theme.border), width=1)
            pairs = [checklist[i:i + 2] for i in range(0, len(checklist), 2)]
            col_w = (card_w - 2 * pad) / 2
            for pair in pairs:
                for j, item in enumerate(pair):
                    tx = x1 + pad + j * col_w
                    item_short = item if len(item) <= 16 else item[:15] + "…"
                    draw.text((tx, cy), "\u2713 " + item_short,
                              fill=buy_color if direction == "BUY" else sell_color, font=font_small)
                cy += line_h

    # ── Trade events overlay (TP HIT / Trade Closed) ────────────
    def _draw_trade_events(self, draw, layout, chart_l, chart_t, chart_r, chart_b):
        drawing = layout.metadata.get("drawing", {}) or {}
        outcome = (layout.metadata.get("original", {}) or {}).get("outcome")

        hits = [f"TP{i} HIT" for i in (1, 2, 3) if drawing.get(f"tp{i}_hit")]
        realized_r = drawing.get("realized_r")
        msg = None
        if hits:
            msg = "   ".join(hits)
            if realized_r is not None:
                msg += f"   {float(realized_r):+.2f}R"
        elif outcome in ("WIN", "LOSS", "BREAK_EVEN") or drawing.get("exit_price") is not None:
            msg = "Trade Closed"
            if realized_r is not None:
                msg += f"   {float(realized_r):+.2f}R"
        if not msg:
            return

        bf = self._get_font(Font(size=13, bold=True))
        bbox = draw.textbbox((0, 0), msg, font=bf)
        tww = bbox[2] - bbox[0]
        th = 26
        tw = tww + 28
        cx = (chart_l + chart_r) / 2
        x1 = max(chart_l + 4, cx - tw / 2)
        x2 = min(chart_r - 4, x1 + tw)
        y1 = chart_t + 10
        y2 = y1 + th
        is_good = ("HIT" in msg or "WIN" in msg or "+" in msg)
        fill = self._theme_color(self.theme.trade_tp if is_good else self.theme.trade_sl)
        draw.rounded_rectangle([x1, y1, x2, y2], radius=th / 2, fill=fill)
        bbox = draw.textbbox((0, 0), msg, font=bf)
        tww = bbox[2] - bbox[0]
        thh = bbox[3] - bbox[1]
        draw.text((x1 + (tw - tww) / 2, y1 + th / 2 - thh / 2 - 1), msg,
                  fill=(255, 255, 255), font=bf)

    # ── Misc ─────────────────────────────────────────────────────
    def _draw_dashed_line(self, draw: ImageDraw, x1: float, y1: float,
                          x2: float, y2: float, color: tuple, width: int = 1,
                          dash_len: int = 6, gap_len: int = 3):
        dx, dy = x2 - x1, y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return
        steps = int(length // (dash_len + gap_len))
        ux, uy = dx / length, dy / length
        for i in range(steps):
            sx = x1 + ux * i * (dash_len + gap_len)
            sy = y1 + uy * i * (dash_len + gap_len)
            ex = sx + ux * dash_len
            ey = sy + uy * dash_len
            draw.line([(sx, sy), (ex, ey)], fill=color, width=width)


_FONT_CACHE_MAP: Dict[str, str] = {}


def _find_font_path(family: str) -> Optional[str]:
    import platform, glob as _glob

    cached = _FONT_CACHE_MAP.get(family)
    if cached:
        return cached if os.path.isfile(cached) else None

    try:
        ImageFont.truetype(family, 10)
        _FONT_CACHE_MAP[family] = family
        return family
    except (OSError, IOError):
        pass

    if platform.system().lower().startswith("win"):
        common_map = {
            "segoe ui": ("segoeui.ttf", "seguisb.ttf", "segoe.ttf"),
            "arial": ("arial.ttf", "arialbd.ttf"),
            "dejavu sans": ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
            "sans-serif": ("segoeui.ttf", "arial.ttf"),
        }
        candidates = common_map.get(family.lower(), [f"{family}.ttf"])
        fonts_dir = "C:\\Windows\\Fonts"
        if os.path.isdir(fonts_dir):
            for candidate in candidates:
                path = os.path.join(fonts_dir, candidate)
                if os.path.isfile(path):
                    try:
                        ImageFont.truetype(path, 10)
                        _FONT_CACHE_MAP[family] = path
                        return path
                    except (OSError, IOError):
                        pass
            pattern = os.path.join(fonts_dir, f"{family}*.ttf")
            for path in _glob.glob(pattern):
                try:
                    ImageFont.truetype(path, 10)
                    _FONT_CACHE_MAP[family] = path
                    return path
                except (OSError, IOError):
                    continue

    return None


def _round_down(value: float, step: float) -> float:
    if step == 0:
        return value
    return math.floor(value / step) * step


def _format_price(value: float, step: float) -> str:
    if step >= 0.05:
        decimals = 2
    elif step >= 0.005:
        decimals = 3
    else:
        decimals = 4
    return f"{value:,.{decimals}f}"


def _format_time(time_str) -> str:
    if not time_str:
        return ""
    # Epoch int/float -> HH:MM
    if isinstance(time_str, (int, float)) and time_str > 1e9:
        try:
            from datetime import datetime
            return datetime.fromtimestamp(time_str).strftime("%H:%M")
        except (ValueError, OSError, OverflowError):
            return ""
    if not isinstance(time_str, str):
        return str(time_str)
    try:
        from datetime import datetime
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(time_str[:19], fmt)
                return dt.strftime("%H:%M")
            except (ValueError, TypeError):
                continue
    except Exception:
        pass
    if len(time_str) >= 16:
        return time_str[11:16]
    if len(time_str) >= 5:
        return time_str[-5:]
    return time_str


def _calc_rr(entry: Optional[float], sl: Optional[float],
             tp_prices) -> Optional[float]:
    if entry is None or sl is None or not tp_prices:
        return None
    try:
        risk = abs(float(entry) - float(sl))
        if risk <= 0:
            return None
        best_tp = max(float(t) for t in tp_prices) if sl > entry else min(float(t) for t in tp_prices)
        return abs(best_tp - float(entry)) / risk
    except (ValueError, TypeError):
        return None


def _first_val(d: dict, key: str) -> Optional[float]:
    v = d.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return v
