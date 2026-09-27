"""Crop TradingView chart canvas to just the candle area."""

import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


def crop_candle_area(image_path: str,
                     output_path: str = None,
                     margin_left: int = 80,
                     margin_right: int = 80,
                     margin_top: int = 30,
                     margin_bottom: int = 40) -> Optional[Tuple[str, dict]]:
    """Crop the chart image to just the candle grid area.

    Returns (output_path, bounds) where bounds = {left, top, width, height}
    describing the candle area within the cropped image.
    """
    if not _PIL_AVAILABLE:
        logger.error("PIL not available")
        return None

    img = Image.open(image_path)
    w, h = img.size

    # Scale factor (retina support)
    scale = max(1, w // 1000)

    # Chart area: remove margins
    cl = margin_left * scale // 2
    cr = margin_right * scale // 2
    ct = margin_top * scale // 2
    cb = margin_bottom * scale // 2

    crop_box = (cl, ct, w - cr, h - cb)
    cropped = img.crop(crop_box)

    if not output_path:
        p = Path(image_path)
        output_path = str(p.parent / f"{p.stem}_cropped{p.suffix}")

    cropped.save(output_path)
    cw, ch = cropped.size
    logger.info("Cropped: %dx%d → %dx%d", w, h, cw, ch)

    # The candle area within the cropped image starts at (0,0) since we cropped margins
    bounds = {"left": 0, "top": 0, "width": cw, "height": ch}
    return output_path, bounds


def auto_crop(image_path: str, output_path: str = None) -> Optional[Tuple[str, dict]]:
    """Auto-detect margins by finding non-background content."""
    # For now, use default estimates
    return crop_candle_area(image_path, output_path)


def get_chart_bounds(image_path: str) -> Optional[dict]:
    """Get the chart bounds from an image (already cropped)."""
    img = Image.open(image_path)
    return {"left": 0, "top": 0, "width": img.width, "height": img.height}


if __name__ == "__main__":
    import sys
    img = sys.argv[1] if len(sys.argv) > 1 else "_tv_test.png"
    res = auto_crop(img)
    if res:
        print(f"Cropped: {res[0]}, bounds={res[1]}")
