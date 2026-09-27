"""Recovery manager — restores TradeLifecycle from open positions on restart.

On bot restart:
    1. Query MT5 (or broker) for all open positions with EA magic number
    2. For each open position, reconstruct the TradePlan and TradeLifecycle
    3. Resume monitoring (BE, partials, trailing) from current state
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from ..simulation.planner import TradePlan
from ..simulation.lifecycle import TradeLifecycle
from ..simulation.result import TradeState

from .broker import BrokerAdapter, PositionInfo, OrderSide, BrokerEvent
from .order_manager import OrderManager, ManagedTrade

logger = logging.getLogger(__name__)


@dataclass
class RecoveredTrade:
    """A trade reconstructed from broker state."""
    ticket: str
    side: str
    entry: float
    current_sl: float
    current_tp: float
    volume: float
    symbol: str
    profit: float
    state: str          # FILLED | BE_SET | TRAILING
    be_moved: bool
    partial_closed: bool


class RecoveryManager:
    """Scans broker for open positions and restores lifecycle state.

    Usage:
        recovery = RecoveryManager(broker, order_manager, magic=202406)
        recovered = recovery.recover()
        for trade in recovered:
            print(trade.ticket, trade.state)
    """

    def __init__(self, broker: BrokerAdapter, order_manager: OrderManager,
                 magic: int = 202406):
        self.broker = broker
        self.om = order_manager
        self.magic = magic

    def recover(self) -> List[RecoveredTrade]:
        """Scan broker for open positions and restore lifecycle.

        Returns:
            List of RecoveredTrade with reconstructed state.
        """
        positions = self._get_ea_positions()
        if not positions:
            logger.info("Recovery: no open positions found")
            return []

        recovered: List[RecoveredTrade] = []
        for pos in positions:
            trade = self._reconstruct(pos)
            if trade:
                self._attach_to_order_manager(trade, pos)
                recovered.append(trade)

        logger.info("Recovery: restored %d/%d positions",
                     len(recovered), len(positions))
        return recovered

    def _get_ea_positions(self) -> List[PositionInfo]:
        """Get open positions filtered by magic number.

        If broker doesn't support magic filtering, get all
        positions and assume all belong to this EA.
        """
        try:
            positions = self.broker.get_all_positions()
            # MT5Adapter's get_all_positions returns all;
            # magic filtering happens at MT5 level via positions_get
            return positions
        except Exception as e:
            logger.error("Recovery: failed to get positions: %s", e)
            return []

    def _reconstruct(self, pos: PositionInfo) -> Optional[RecoveredTrade]:
        """Infer lifecycle state from position info.

        Heuristics:
            - SL == entry → BE_SET
            - SL > entry (BUY) or SL < entry (SELL) → TRAILING
            - else → FILLED
        """
        side = "BUY" if pos.side == OrderSide.BUY else "SELL"
        be_moved = False
        partial_closed = False
        state = TradeState.FILLED

        # Check if BE was moved
        if pos.side == OrderSide.BUY and pos.stop_loss >= pos.open_price:
            be_moved = True
            if pos.stop_loss > pos.open_price:
                state = TradeState.TRAILING
            else:
                state = TradeState.BE_SET
        elif pos.side == OrderSide.SELL and pos.stop_loss <= pos.open_price:
            be_moved = True
            if pos.stop_loss < pos.open_price:
                state = TradeState.TRAILING
            else:
                state = TradeState.BE_SET

        # Partial close detection: if volume is not a standard lot
        # we infer partial closure happened (this is best-effort)
        # A more reliable method is to compare against planned volume

        return RecoveredTrade(
            ticket=pos.ticket,
            side=side,
            entry=pos.open_price,
            current_sl=pos.stop_loss,
            current_tp=pos.take_profit,
            volume=pos.volume,
            symbol=pos.symbol,
            profit=pos.profit,
            state=state,
            be_moved=be_moved,
            partial_closed=partial_closed,
        )

    def _attach_to_order_manager(self, trade: RecoveredTrade,
                                  pos: PositionInfo):
        """Build a TradePlan + lifecycle and register in OrderManager.

        This is a best-effort reconstruction. The TP levels are inferred
        from the current TP; partial fills are not tracked across restart.
        """
        # Build a minimal TradePlan approximating the open position
        plan = TradePlan(
            side=trade.side,
            entry=trade.entry,
            stop_loss=trade.current_sl,
            take_profits=[trade.current_tp] if trade.current_tp else [],
            risk_percent=0.5,  # unknown after restart
            partials=[1.0],
            label=trade.symbol,
        )

        # Rebuild lifecycle in correct state
        lc = TradeLifecycle(plan)
        lc.state = trade.state
        lc.current_sl = trade.current_sl
        lc.current_tp_index = 1 if trade.state in ("BE_SET", "TRAILING") else 0

        if trade.be_moved:
            lc.breakeven._activated = True
            lc.breakeven._be_price = trade.entry

        # Register in OrderManager
        mt = ManagedTrade(
            ticket=trade.ticket,
            plan=plan,
            lifecycle=lc,
            volume=trade.volume,
            symbol=trade.symbol,
            status="ACTIVE",
        )
        self.om._trades[trade.ticket] = mt
        logger.info("Recovery: attached %s %s ticket=%s state=%s",
                     trade.side, trade.symbol, trade.ticket, trade.state)
