from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from api.services.screenshot_sign import verify_screenshot_signature

SCREENSHOTS_DIR = Path(__file__).resolve().parents[2] / "storage" / "screenshots"

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screenshots", tags=["screenshots"])

_ALLOWED_TYPES = ("entry", "exit", "management")


@router.get("/{trade_id}/{type}")
async def get_screenshot(
    trade_id: str,
    type: str = "entry",
    exp: str = Query(...),
    sig: str = Query(...),
):
    if type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Invalid type. Use: entry, exit, management")
    if not verify_screenshot_signature(trade_id, f"{type}.png", exp, sig):
        raise HTTPException(status_code=403, detail="Invalid or expired screenshot link")
    path = SCREENSHOTS_DIR / trade_id / f"{type}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(str(path), media_type="image/png")
