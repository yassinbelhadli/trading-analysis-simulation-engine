from __future__ import annotations
import logging

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core_engine.detection.setup_detector import SetupCandidate
from core_engine.execution.trade_planner import TradePlan, TradePlanner
from core_engine.execution.order_manager import OrderManager, OrderResult
from core_engine.execution.execution_guard import ExecutionGuard, GuardResult
from core_engine.execution.broker import MT5Broker, PaperBroker
from core_engine.mt_runtime import MTRuntime
from core_engine.risk.account_profile import AccountProfile
from core_engine.mt5_runtime import MT5Runtime

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    success: bool
    plan: Optional[TradePlan]
    order: Optional[OrderResult]
    message: str
    guard_result: Optional[GuardResult] = None


class ExecutionEngine:
    def __init__(
        self,
        runtime: MTRuntime,
        trade_planner: Optional[TradePlanner] = None,
        order_manager: Optional[OrderManager] = None,
        account_id: str = "",
        user_id: str = "",
    ):
        self.runtime = runtime
        self.trade_planner = trade_planner or TradePlanner()
        if order_manager is None:
            broker = MT5Broker(runtime) if isinstance(runtime, MT5Runtime) else PaperBroker()
            self.order_manager = OrderManager(broker)
        else:
            self.order_manager = order_manager
        self.guard = ExecutionGuard(runtime, account_id, user_id) if account_id else None

    async def execute_candidate(
        self,
        candidate: SetupCandidate,
        profile: AccountProfile,
        current_price: float,
        account_id: str = "",
        user_id: str = "",
        trade_mode: str = "CONSERVATIVE",
    ) -> ExecutionResult:
        if candidate is None:
            return ExecutionResult(False, None, None, "No setup candidate.")

        if candidate.score_result and candidate.score_result.recommendation != "EXECUTE":
            return ExecutionResult(
                False, None, None,
                f"Setup not executable: {candidate.score_result.recommendation}",
            )

        plan = self.trade_planner.plan(
            candidate=candidate,
            profile=profile,
            current_price=current_price,
        )

        if not plan.valid:
            logger.warning("Invalid trade plan | symbol=%s direction=%s", candidate.symbol, candidate.direction)
            return ExecutionResult(False, plan, None, "Invalid trade plan.")

        # --- Execution Guard ---
        guard = self.guard or (ExecutionGuard(self.runtime, account_id, user_id) if account_id else None)
        if guard is not None:
            guard_result = await guard.can_execute(
                symbol=candidate.symbol, direction=candidate.direction,
                trade_mode=trade_mode,
            )
            if not guard_result.allowed:
                logger.warning("Guard blocked | symbol=%s direction=%s reason=%s",
                               candidate.symbol, candidate.direction, guard_result.reason)
                return ExecutionResult(
                    False, plan, None,
                    f"Guard blocked: {guard_result.reason}",
                    guard_result=guard_result,
                )
        else:
            logger.warning("No guard configured — bypassing safety checks")

        logger.info("Placing order | symbol=%s direction=%s lot=%s entry=%s sl=%s tp=%s",
                    candidate.symbol, candidate.direction, plan.lot_size,
                    plan.entry_price, plan.stop_loss, plan.take_profit)
        order = await self.order_manager.place_order(plan)

        if not order.success:
            return ExecutionResult(False, plan, order, order.message)

        return ExecutionResult(True, plan, order, "Order placed successfully.")
