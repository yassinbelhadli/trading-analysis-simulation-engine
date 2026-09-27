"""Signal card: clean chart + ICT overlays + price label on right."""

import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from chart_renderer.coordinate_mapper import CoordMapper
from chart_renderer.draw_order_blocks import draw_ob
from chart_renderer.draw_fvg import draw_fvg
from chart_renderer.draw_structure import draw_structure, BOS_CLR, CH_CLR, MSS_CLR
from chart_renderer.draw_trade import draw_trade
from chart_renderer.draw_labels import draw_swings, draw_sweep, draw_pdh_pdl
from chart_renderer.draw_utils import FONT_SMALL

CARD_W = 1200
CARD_H = 900

# Widget layout (CSS px)
WIDGET_W       = 1398
WIDGET_H       = 898
CHART_AREA_W   = 1344
CHART_AREA_H   = 870

# Chart area within the resized card
MAP_W = CARD_W * CHART_AREA_W // WIDGET_W    # 1153
MAP_H = CARD_H * CHART_AREA_H // WIDGET_H    # 871

DARK_BG = (13, 17, 28)
WHITE   = (255, 255, 255)
GRAY    = (140, 145, 158)
GREEN   = (0, 200, 83)
RED     = (255, 82, 82)


def render_card(chart_image_path: str,
                symbol: str,
                timeframe: str,
                direction: str,
                entry_price: float,
                sl_price: float,
                tp_price: float,
                ohlc_count: int = 100,
                visible_end_index: int = None,
                signal_data: Dict = None,
                confidence: float = 94,
                price_range: dict = None,
                output_path: str = None) -> Optional[str]:
    if not _PIL_AVAILABLE:
        logger.error("PIL not available")
        return None

    sd = signal_data or {}
    chart_img = Image.open(chart_image_path).convert("RGBA")

    card = Image.new("RGBA", (CARD_W, CARD_H), DARK_BG)
    draw = ImageDraw.Draw(card)

    chart_resized = chart_img.resize((CARD_W, CARD_H), Image.LANCZOS)
    card.paste(chart_resized, (0, 0))

    # Full chart area bounds — lines stop before price axis (right) and time axis (bottom)
    clamp = (0, 0, MAP_W, MAP_H)

    # Coordinate mapper — use actual chart visible range when available
    if price_range and price_range.get("price_high") and price_range.get("price_low"):
        p_high = price_range["price_high"]
        p_low = price_range["price_low"]
    else:
        # Fallback: calculate from trade/indicator prices
        all_prices = [entry_price, sl_price, tp_price]
        for sw in (sd.get("swings") or []):
            p = sw.get("price")
            if p: all_prices.append(p)
        for ob in (sd.get("order_blocks") or []):
            for k in ("top", "bottom"):
                v = ob.get(k)
                if v: all_prices.append(v)
        for f in (sd.get("fvgs") or []):
            for k in ("top", "bottom"):
                v = f.get(k)
                if v: all_prices.append(v)
        for k in ("sweep_price", "pdh", "pdl"):
            v = sd.get(k)
            if v: all_prices.append(v)
        pad_ratio = 0.12
        p_low = min(all_prices) - (max(all_prices) - min(all_prices)) * pad_ratio
        p_high = max(all_prices) + (max(all_prices) - min(all_prices)) * pad_ratio

    end_idx = visible_end_index or ohlc_count
    m = CoordMapper(0, 0, MAP_W, MAP_H, p_high, p_low, 0, end_idx)

    draw_ob(draw, sd.get("ob") or (sd.get("order_blocks") or [None])[0], m, clamp)
    draw_fvg(draw, sd.get("fvg") or (sd.get("fvgs") or [None])[0], m, clamp)
    for key, label, clr in [("bos", "BOS", BOS_CLR), ("choch", "CHoCH", CH_CLR), ("mss", "MSS", MSS_CLR)]:
        draw_structure(draw, key, label, clr, sd.get(key), m, clamp)
    draw_swings(draw, sd.get("swings") or [], m, clamp)
    draw_sweep(draw, sd.get("sweep_price"), sd.get("sweep_type", ""), m, clamp)
    draw_pdh_pdl(draw, sd.get("pdh"), sd.get("pdl"), m, clamp)
    draw_trade(draw, entry_price, sl_price, tp_price, direction, m, clamp)

    # Trade badges just LEFT of the price scale (price scale stays clean)
    for ltext, p, clr in [("TP", tp_price, GREEN), ("ENTRY", entry_price, GREEN if direction.upper() == "BUY" else RED), ("SL", sl_price, RED)]:
        py = int(m.y_line(p))
        # Small tick on the chart edge
        draw.line([(MAP_W - 3, py), (MAP_W, py)], fill=clr, width=2)
        # Colored circle + label sitting left of the price scale
        cr = 3
        cx = MAP_W - 10
        draw.ellipse([(cx - cr, py - cr), (cx + cr, py + cr)], fill=clr)
        draw.text((cx + cr + 3, py), ltext, fill=clr, font=FONT_SMALL, anchor="lm")

    # BUY / SELL badge with confidence
    is_buy = direction.upper() == "BUY"
    badge_text = f"BUY | {confidence:.0f}%" if is_buy else f"SELL | {confidence:.0f}%"
    badge_clr = GREEN if is_buy else RED
    circle_r = 4
    pad_b = 6
    bb = draw.textbbox((0, 0), badge_text, font=FONT_SMALL)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    cx = 14 + circle_r
    cy = 14
    b_left = cx - circle_r - pad_b
    b_top = cy - th // 2 - pad_b
    b_right = cx + circle_r + tw + pad_b * 2
    b_bot = cy + th // 2 + pad_b
    draw.rounded_rectangle([b_left, b_top, b_right, b_bot], radius=6, fill=DARK_BG + (200,))
    draw.ellipse([(cx - circle_r, cy - circle_r), (cx + circle_r, cy + circle_r)], fill=badge_clr)
    draw.text((cx + circle_r + pad_b, cy), badge_text, fill=WHITE, font=FONT_SMALL, anchor="lm")

    if not output_path:
        p = Path(chart_image_path)
        output_path = str(p.parent / f"signal_{p.stem}.png")
    card = card.convert("RGB")
    card.save(output_path, "PNG")
    logger.info("Signal card: %s", output_path)
    return output_path
