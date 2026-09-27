"""Generate professional signal card: TradingView chart + branding + selective ICT overlays."""

import logging
import math
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# ── Color palette ──
DARK_BG    = (13, 17, 28)    # card background
DARK2      = (22, 28, 42)    # section header
WHITE      = (255, 255, 255)
GRAY       = (140, 145, 158)
GRAY_LIGHT = (180, 185, 198)
GREEN      = (0, 200, 83)
RED        = (255, 82, 82)
BLUE       = (41, 98, 255)
GOLD       = (255, 215, 0)
CYAN       = (0, 188, 212)
PINK       = (233, 30, 99)
ORANGE     = (255, 152, 0)

# ICT concept colors
ICT_OB_BULL  = (37, 99, 235)
ICT_OB_BEAR  = (147, 51, 234)
ICT_FVG_BULL = (34, 197, 94)
ICT_FVG_BEAR = (239, 68, 68)
ICT_BOS      = (6, 182, 212)
ICT_CHOCH    = (245, 158, 11)
ICT_MSS      = (236, 72, 153)

# ── Fonts (try Segoe UI for Windows, fallback) ──
def _load_font(size):
    for name in ["Segoe UI", "Arial", "DejaVuSans", "LiberationSans"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_BOLD  = _load_font(13)
FONT_NORM  = _load_font(11)
FONT_SMALL = _load_font(9)
FONT_LOGO  = _load_font(14)
FONT_TITLE = _load_font(16)

# ── Layout constants (pixels) ──
CARD_W = 1200
CARD_H = 900
HEADER_H = 70
FOOTER_H = 110
CHART_Y_START = HEADER_H
CHART_H = CARD_H - HEADER_H - FOOTER_H

# Margins for chart content
CHART_MARGIN_LEFT = 80
CHART_MARGIN_RIGHT = 30
CHART_MARGIN_TOP = 10
CHART_MARGIN_BOTTOM = 10


def generate_card(chart_path: str,
                  symbol: str,
                  timeframe: str,
                  direction: str,
                  entry_price: float,
                  sl_price: float,
                  tp_prices: List[float],
                  icp_data: Dict = None,
                  confidence: float = 94.0,
                  risk_pct: float = 1.0,
                  rr: float = 3.0,
                  session: str = "London",
                  output_path: str = None) -> Optional[str]:
    """Create a professional ICT signal card.

    Args:
        chart_path: Path to captured TradingView chart PNG.
        symbol: Trading symbol (e.g. 'BTCUSD').
        timeframe: e.g. 'M15'.
        direction: 'BUY' or 'SELL'.
        entry/sl/tp: Trade prices.
        icp_data: Dict with ICT concepts:
            bos: {start_index, end_index, price}
            choch: {start_index, end_index, price}
            mss: {start_index, end_index, price}
            ob: {type, top, bottom, fresh, mitigated}
            fvg: {type, top, bottom, mitigated}
            swing: {type, price, index}
            sweep_price, sweep_type
            pdh, pdl
        confidence: Signal confidence percentage.
        risk_pct: Risk as % of account.
        rr: Risk:Reward ratio.
        session: Trading session label.
    """
    if not _PIL_AVAILABLE:
        logger.error("PIL not available")
        return None

    # Load chart image
    chart_img = Image.open(chart_path).convert("RGBA")

    # Create card canvas
    card = Image.new("RGBA", (CARD_W, CARD_H), DARK_BG)
    draw = ImageDraw.Draw(card)

    # ── 1. Header ──
    _draw_header(draw, symbol, timeframe, direction, confidence)

    # ── 2. Chart body ──
    chart_area = chart_img.resize(
        (CARD_W - CHART_MARGIN_LEFT - CHART_MARGIN_RIGHT, CHART_H - CHART_MARGIN_TOP - CHART_MARGIN_BOTTOM),
        Image.LANCZOS
    )
    card.paste(chart_area, (CHART_MARGIN_LEFT, CHART_Y_START + CHART_MARGIN_TOP))
    card_chart_left = CHART_MARGIN_LEFT
    card_chart_top = CHART_Y_START + CHART_MARGIN_TOP
    card_chart_w = chart_area.width
    card_chart_h = chart_area.height

    # Divider
    draw.line([(0, CHART_Y_START), (CARD_W, CHART_Y_START)], fill=DARK2, width=2)
    draw.line([(0, CARD_H - FOOTER_H), (CARD_W, CARD_H - FOOTER_H)], fill=DARK2, width=2)

    # ── 3. ICT overlays on chart area ──
    icp = icp_data or {}
    price_range = icp.get("price_range", {})
    p_high = price_range.get("high")
    p_low = price_range.get("low")

    # Auto-calculate price range from trade levels if not available
    if not p_high or not p_low:
        all_prices = [entry_price, sl_price] + tp_prices
        for sw in (icp.get("swings") or []):
            p = sw.get("price")
            if p: all_prices.append(p)
        for ob in (icp.get("order_blocks") or []):
            for k in ("top", "bottom"):
                v = ob.get(k)
                if v: all_prices.append(v)
        for f in (icp.get("fvgs") or []):
            for k in ("top", "bottom"):
                v = f.get(k)
                if v: all_prices.append(v)
        for k in ("sweep_price", "pdh", "pdl"):
            v = icp.get(k)
            if v: all_prices.append(v)
        if all_prices:
            pad = (max(all_prices) - min(all_prices)) * 0.15
            p_high = max(all_prices) + pad
            p_low = min(all_prices) - pad
        else:
            p_high = entry_price * 1.05
            p_low = entry_price * 0.95

    def _y(price):
        frac = (price - p_low) / (p_high - p_low)
        return int(card_chart_top + card_chart_h - frac * card_chart_h)

    # Draw ICT concepts
    _draw_ict_concepts(draw, icp, _y, card_chart_left, card_chart_top, card_chart_w, card_chart_h)

    # ── 4. Trade lines ──
    _draw_trade_lines(draw, entry_price, sl_price, tp_prices, direction, _y,
                      card_chart_left, card_chart_top, card_chart_w, card_chart_h)

    # ── 5. Footer ──
    _draw_footer(draw, entry_price, sl_price, tp_prices, direction,
                 risk_pct, rr, session, timeframe)

    # Save
    if not output_path:
        p = Path(chart_path)
        output_path = str(p.parent / f"signal_{p.stem}.png")
    card = card.convert("RGB")
    card.save(output_path, "PNG")
    logger.info("Signal card saved: %s", output_path)
    return output_path


def _draw_header(draw, symbol, timeframe, direction, confidence):
    """Draw card header: logo + symbol info + confidence + bias."""
    # Background
    draw.rectangle([(0, 0), (CARD_W, HEADER_H)], fill=DARK2)

    # Logo
    logo_text = "ICT EA PRO"
    draw.text((18, HEADER_H // 2 - 1), logo_text, fill=BLUE, font=FONT_LOGO, anchor="lm")

    # Separator
    draw.line([(140, 15), (140, HEADER_H - 15)], fill=GRAY, width=1)

    # Symbol + Timeframe
    draw.text((155, HEADER_H // 2 - 1), f"{symbol} | {timeframe}",
              fill=WHITE, font=FONT_TITLE, anchor="lm")

    # Direction badge
    is_buy = direction.upper() == "BUY"
    badge_clr = GREEN if is_buy else RED
    badge_text = "  BUY  " if is_buy else "  SELL  "
    bb = draw.textbbox((0, 0), badge_text, font=FONT_BOLD)
    bw, bh = bb[2] - bb[0] + 12, bb[3] - bb[1] + 8
    bx = 380
    by = HEADER_H // 2 - bh // 2
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=4, fill=badge_clr)
    draw.text((bx + 6, by + 4), badge_text, fill=WHITE, font=FONT_BOLD, anchor="la")

    # Confidence
    cf_text = f"Confidence: {confidence:.0f}%"
    draw.text((CARD_W - 200, HEADER_H // 2 - 1), cf_text,
              fill=GOLD, font=FONT_BOLD, anchor="lm")


def _draw_ict_concepts(draw, icp, _y, cx, cy, cw, ch):
    """Draw selective ICT concepts on chart area."""
    def _lbl(text, x, y, bg, fg=(255,255,255,255), font=None, pad=4):
        f = font or FONT_SMALL
        bb = draw.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        bx, by = x - tw // 2 - pad, y - th // 2 - pad
        bx2, by2 = x + tw // 2 + pad, y + th // 2 + pad
        # Clamp
        bx = max(cx + 4, min(bx, cx + cw - tw - pad * 2 - 4))
        bx2 = bx + tw + pad * 2
        draw.rounded_rectangle([bx, by, bx2, by2], radius=3, fill=bg)
        draw.text((bx + pad, by + pad), text, fill=fg, font=f, anchor="la")

    # BOS / CHoCH / MSS
    for key, label, clr in [("bos", "BOS", ICT_BOS), ("choch", "CHoCH", ICT_CHOCH), ("mss", "MSS", ICT_MSS)]:
        d = icp.get(key)
        if d and isinstance(d, dict):
            price = d.get("price")
            if price is not None:
                y = _y(price)
                draw.line([(cx + 20, y), (cx + cw - 10, y)], fill=clr + (200,), width=2)
                mc = cx + cw // 2
                draw.line([(mc - 30, y), (mc + 30, y)], fill=clr + (240,), width=3)
                _lbl(label, mc, y - 14, clr + (220,))

    # Swing (last 2)
    for sw in (icp.get("swings") or [])[-2:]:
        p = sw.get("price")
        t = sw.get("type", "")
        if p:
            y = _y(p)
            above = t in ("HH", "LH")
            off = -16 if above else 16
            _lbl(t, cx + cw - 35, y + off, DARK2 + (200,))

    # Order Block
    ob = icp.get("order_blocks")
    if isinstance(ob, list) and ob:
        ob = ob[0]
        top, bot = ob.get("top"), ob.get("bottom")
        if top and bot:
            y0, y1 = _y(max(top, bot)), _y(min(top, bot))
            oc = ICT_OB_BULL if "Bullish" in ob.get("type", "") else ICT_OB_BEAR
            rect_w = min(cw - 40, 120)
            xe = cx + cw - 20
            draw.rectangle([xe - rect_w, y0, xe, y1], fill=oc + (40,))
            draw.rectangle([xe - rect_w, y0, xe, y1], outline=oc + (160,), width=1)
            _lbl("OB", xe - rect_w // 2, (y0 + y1) // 2, oc + (200,))

    # FVG
    f = icp.get("fvgs")
    if isinstance(f, list) and f:
        f = f[0]
        top, bot = f.get("top"), f.get("bottom")
        if top and bot:
            y0, y1 = _y(max(top, bot)), _y(min(top, bot))
            fc = ICT_FVG_BULL if "Bullish" in f.get("type", "") else ICT_FVG_BEAR
            rect_w = min(cw - 40, 100)
            xe = cx + cw - 20
            draw.rectangle([xe - rect_w, y0, xe, y1], fill=fc + (25,))
            _lbl("FVG", xe - rect_w // 2, (y0 + y1) // 2, fc + (200,))

    # Sweep / PDH / PDL
    sp = icp.get("sweep_price")
    if sp:
        y = _y(sp)
        draw.line([(cx + 30, y), (cx + cw - 30, y)], fill=PINK + (60,), width=1, )
        _lbl(f"Sweep {icp.get('sweep_type', '')}", cx + 40, y, PINK + (180,))

    pdh = icp.get("pdh")
    if pdh:
        _lbl("PDH", cx + cw - 40, _y(pdh), CYAN + (180,))
    pdl = icp.get("pdl")
    if pdl:
        _lbl("PDL", cx + cw - 40, _y(pdl), ORANGE + (180,))


def _draw_trade_lines(draw, entry_price, sl_price, tp_prices, direction, _y,
                      cx, cy, cw, ch):
    """Draw Entry / SL / TP lines on chart area."""
    is_buy = direction.upper() == "BUY"
    ey = _y(entry_price)

    # Entry marker (triangle + line)
    draw.line([(cx + 10, ey), (cx + cw - 10, ey)], fill=WHITE + (200,), width=2)
    tri_color = GREEN if is_buy else RED
    draw.polygon([(cx + 15, ey), (cx + 28, ey - 7), (cx + 28, ey + 7)], fill=tri_color)
    _draw_label_box(draw, f"Entry {entry_price:.2f}", cx + 50, ey - 16, DARK2 + (220,), WHITE)

    # SL
    sy = _y(sl_price)
    draw.line([(cx + 50, sy), (cx + cw - 10, sy)], fill=RED + (200,), width=2, )
    _draw_label_box(draw, f"SL {sl_price:.2f}", cx + 50, sy - 16, RED + (180,), WHITE)

    # TP lines
    for i, tp in enumerate(tp_prices, 1):
        ty = _y(tp)
        draw.line([(cx + 50, ty), (cx + cw - 10, ty)], fill=GREEN + (200,), width=2)
        _draw_label_box(draw, f"TP{i} {tp:.2f}", cx + 50, ty - 16, GREEN + (180,), WHITE)


def _draw_label_box(draw, text, x, y, bg, fg, font=None):
    """Draw a rounded label box at (x,y) with text."""
    f = font or FONT_NORM
    bb = draw.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad = 4
    bx, by = x, y
    bx2, by2 = bx + tw + pad * 2, by + th + pad * 2
    draw.rounded_rectangle([bx, by, bx2, by2], radius=3, fill=bg)
    draw.text((bx + pad, by + pad), text, fill=fg, font=f, anchor="la")


def _draw_footer(draw, entry_price, sl_price, tp_prices, direction,
                 risk_pct, rr, session, timeframe):
    """Draw footer with trade details."""
    fy = CARD_H - FOOTER_H

    # Background
    draw.rectangle([(0, fy), (CARD_W, CARD_H)], fill=DARK2)

    is_buy = direction.upper() == "BUY"

    # Calculate RR
    if sl_price and entry_price:
        if is_buy:
            risk = entry_price - sl_price
            rr_pips = [(tp - entry_price) / risk for tp in tp_prices if tp]
        else:
            risk = sl_price - entry_price
            rr_pips = [(entry_price - tp) / risk for tp in tp_prices if tp]
        rr_str = f"RR: 1:{max(rr_pips):.1f}" if rr_pips else f"RR: 1:{rr:.1f}"
    else:
        rr_str = f"RR: 1:{rr:.1f}"

    items = [
        (f"Entry: {entry_price:.2f}", WHITE),
        (f"SL: {sl_price:.2f}", RED),
    ]
    for i, tp in enumerate(tp_prices, 1):
        items.append((f"TP{i}: {tp:.2f}", GREEN))

    # Draw items
    x_start = 30
    y_text = fy + 18
    for text, clr in items:
        draw.text((x_start, y_text), text, fill=clr, font=FONT_NORM, anchor="la")
        x_start += 150

    # Risk info
    x_start = 30
    y_text = fy + 50
    for text in [f"Risk: {risk_pct:.1f}%", f"{rr_str}", f"Session: {session}", f"TF: {timeframe}"]:
        draw.text((x_start, y_text), text, fill=GRAY_LIGHT, font=FONT_SMALL, anchor="la")
        x_start += 160

    # Brand watermark
    draw.text((CARD_W - 20, CARD_H - 14), "ictfundedea.com",
              fill=GRAY, font=FONT_SMALL, anchor="rb")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    img = sys.argv[1] if len(sys.argv) > 1 else None
    if not img or not Path(img).exists():
        print("Usage: python image_generator.py <chart_image.png>")
        sys.exit(1)
    out = generate_card(img, "BTCUSD", "M15", "BUY", 64200, 63600, [64600, 65000],
                        session="London", confidence=94)
    if out:
        print(f"OK: {out}")
