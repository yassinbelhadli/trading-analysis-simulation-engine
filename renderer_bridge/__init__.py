"""Renderer Bridge — maps Detection/Execution data → Renderer V2 Scene → output.

Pipeline:
    SetupCandidate/TradeResult/PositionInfo
        → mapper (canonical snapshot)
        → Scene (via builder pipeline)
        → LayoutScene (via CoordMapper)
        → PIL Image (via PILBackend)
"""

from .setup_mapper import setup_to_scene
from .trade_mapper import trade_to_scene
from .position_mapper import position_to_scene
from .render_service import RenderService

__all__ = [
    "setup_to_scene",
    "trade_to_scene",
    "position_to_scene",
    "RenderService",
]
