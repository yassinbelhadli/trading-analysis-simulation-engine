from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set

from core_engine.execution.trade_planner import TradePlan
from core_engine.mt_runtime import MTRuntime, MTPosition


@dataclass
class TradeManagementAction:
    action: str
    ticket: int
    message: str
    new_sl: Optional[float] = None
    close_volume: Optional[float] = None


class TradeManager:
    def __init__(self, runtime: MTRuntime, trail_mult: float = 0.75):
        self.runtime = runtime
        self.trail_mult = trail_mult
        self._partial_closed_tickets: Set[int] = set()

    def _trailing_sl(self, position: MTPosition, plan: TradePlan, r_multiple: float) -> Optional[TradeManagementAction]:
        risk = abs(plan.entry_price - plan.stop_loss)
        trail_distance = risk * self.trail_mult

        if plan.direction == "BUY":
            new_sl = position.current_price - trail_distance
            if r_multiple >= 1.5 and new_sl > position.stop_loss:
                return TradeManagementAction(
                    action="TRAIL_SL", ticket=position.ticket,
                    message="Trailing stop updated.", new_sl=round(new_sl, 2),
                )

        else:
            new_sl = position.current_price + trail_distance
            if r_multiple >= 1.5 and new_sl < position.stop_loss:
                return TradeManagementAction(
                    action="TRAIL_SL", ticket=position.ticket,
                    message="Trailing stop updated.", new_sl=round(new_sl, 2),
                )

        return None

    def manage_position(
        self,
        position: MTPosition,
        plan: TradePlan,
    ) -> List[TradeManagementAction]:
        actions: List[TradeManagementAction] = []

        risk = abs(plan.entry_price - plan.stop_loss)
        if risk <= 0:
            return actions

        if plan.direction == "BUY":
            profit_distance = position.current_price - plan.entry_price
        else:
            profit_distance = plan.entry_price - position.current_price

        r_multiple = profit_distance / risk

        if r_multiple >= 1.0 and position.stop_loss != plan.entry_price:
            actions.append(
                TradeManagementAction(
                    action="MOVE_BE",
                    ticket=position.ticket,
                    message="Move stop loss to break-even.",
                    new_sl=plan.entry_price,
                )
            )

        if r_multiple >= 1.5 and position.ticket not in self._partial_closed_tickets:
            actions.append(
                TradeManagementAction(
                    action="PARTIAL_CLOSE",
                    ticket=position.ticket,
                    message="Take partial profit.",
                    close_volume=round(position.volume * 0.5, 2),
                )
            )

        trail = self._trailing_sl(position, plan, r_multiple)
        if trail:
            actions.append(trail)

        return actions

    async def apply_actions(
        self,
        actions: List[TradeManagementAction],
    ) -> List[TradeManagementAction]:
        applied: List[TradeManagementAction] = []

        for action in actions:
            if action.action == "MOVE_BE" and action.new_sl is not None:
                ok = await self.runtime.modify_sl(action.ticket, action.new_sl)
                if ok:
                    applied.append(action)

            elif action.action == "TRAIL_SL" and action.new_sl is not None:
                ok = await self.runtime.modify_sl(action.ticket, action.new_sl)
                if ok:
                    applied.append(action)

            elif action.action == "PARTIAL_CLOSE" and action.close_volume is not None:
                ok = await self.runtime.partial_close(action.ticket, action.close_volume)
                if ok:
                    self._partial_closed_tickets.add(action.ticket)
                    applied.append(action)

        return applied

    def check_close(
        self,
        position: MTPosition,
        plan: TradePlan,
    ) -> Optional[TradeManagementAction]:
        if plan.direction == "BUY":
            if position.current_price <= position.stop_loss:
                return TradeManagementAction(
                    action="CLOSE", ticket=position.ticket,
                    message="Stop loss hit.",
                )
            if position.current_price >= position.take_profit:
                return TradeManagementAction(
                    action="CLOSE", ticket=position.ticket,
                    message="Take profit hit.",
                )

        else:
            if position.current_price >= position.stop_loss:
                return TradeManagementAction(
                    action="CLOSE", ticket=position.ticket,
                    message="Stop loss hit.",
                )
            if position.current_price <= position.take_profit:
                return TradeManagementAction(
                    action="CLOSE", ticket=position.ticket,
                    message="Take profit hit.",
                )

        return None

    async def tick(
        self,
        position: MTPosition,
        plan: TradePlan,
    ) -> List[TradeManagementAction]:
        actions = self.manage_position(position, plan)
        close = self.check_close(position, plan)

        if close:
            return [close]

        if actions:
            return await self.apply_actions(actions)

        return []
