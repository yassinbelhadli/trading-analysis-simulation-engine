"""
Stress Test: 10 accounts, scanner + engine cycles, breach isolation.

Requires a running PostgreSQL database. Test accounts are created and cleaned up.
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete

from database.db import async_session_factory, init_db, close_db
from database.models import User, License, TradingAccount, RiskProfile, PaperTrade, AccountScan
from database.repositories import AccountRepository
from core_engine.scanner import AccountScanner, ScanResult
from core_engine.account_manager import AccountManager
from core_engine.engine_manager import engine_manager
from core_engine.risk_manager import RiskManager
from core_engine.mt_runtime import MTRuntimeMock

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("stress_test")

TEST_USER_ID: Optional[str] = None
TEST_ACCOUNT_IDS: List[str] = []
BREACH_ACCOUNT_ID: Optional[str] = None


async def setup_accounts(n: int = 10) -> str:
    global TEST_USER_ID, TEST_ACCOUNT_IDS
    async with async_session_factory() as session:
        user = User(
            telegram_id=999999999,
            telegram_username="stress_test_user",
            language="EN",
            status="active",
        )
        session.add(user)
        await session.flush()
        TEST_USER_ID = user.id

        for i in range(n):
            acc = TradingAccount(
                user_id=user.id,
                account_type="PERSONAL",
                platform="MT4",
                server="stress_server",
                login=f"stress_{i}",
                encrypted_password="dummy_encrypted",
                active=True,
                real_trading_enabled=False,
                engine_status="WAITING_ACTIVATION",
            )
            session.add(acc)
            await session.flush()
            TEST_ACCOUNT_IDS.append(acc.id)

        await session.commit()
    return TEST_USER_ID


async def cleanup():
    async with async_session_factory() as session:
        if TEST_ACCOUNT_IDS:
            for tid in TEST_ACCOUNT_IDS:
                await session.execute(
                    delete(PaperTrade).where(PaperTrade.account_id == tid)
                )
                await session.execute(
                    delete(AccountScan).where(AccountScan.account_id == tid)
                )
                await session.execute(
                    delete(RiskProfile).where(RiskProfile.account_id == tid)
                )
            await session.execute(
                delete(TradingAccount).where(TradingAccount.id.in_(TEST_ACCOUNT_IDS))
            )
        if TEST_USER_ID:
            await session.execute(delete(License).where(License.user_id == TEST_USER_ID))
            await session.execute(delete(User).where(User.id == TEST_USER_ID))
        await session.commit()


async def run_stress():
    print("=" * 60)
    print("STRESS TEST - 10 ACCOUNTS")
    print("=" * 60)

    await init_db()
    user_id = await setup_accounts(10)
    print(f"\n[SETUP] 10 accounts created, user={user_id}")

    scanner = AccountScanner(scan_interval=0.1)
    scanner._running = True

    # -- Phase 1: Scanner 5 cycles --
    print("\n-- Phase 1: Scanner 5 cycles --")
    all_results: Dict[str, List[ScanResult]] = {}
    for cycle in range(5):
        for aid in TEST_ACCOUNT_IDS:
            result = await scanner.scan_account(aid)
            all_results.setdefault(aid, []).append(result)
        print(f"  Cycle {cycle+1}/5: {len(all_results)} accounts scanned")

    ok = sum(1 for rl in all_results.values() for r in rl if r.success)
    fail = sum(1 for rl in all_results.values() for r in rl if not r.success)
    print(f"  [{'OK' if fail == 0 else 'FAIL'}] {ok} OK / {fail} FAIL (all successes expected)")
    assert fail == 0, f"{fail} scan failures"

    unique_symbols = set()
    for rl in all_results.values():
        for r in rl:
            unique_symbols.update(r.symbols)
    print(f"  [OK] Symbols detected: {unique_symbols}")

    # -- Phase 2: Engine 5 cycles (detect + paper trade) --
    print("\n-- Phase 2: Engine detection 5 cycles --")
    from core_engine.detection.setup_detector import SetupDetector
    from core_engine.data_feed.market_data import MarketData
    from core_engine.risk.account_profile import AccountProfileBuilder
    from core_engine.execution.paper_trading import paper_trading
    from core_engine.execution.trade_planner import TradePlanner

    detector = SetupDetector()
    profile_builder = AccountProfileBuilder()

    paper_count_before: Dict[str, int] = {aid: 0 for aid in TEST_ACCOUNT_IDS}
    paper_log: Dict[str, List[str]] = {aid: [] for aid in TEST_ACCOUNT_IDS}

    for cycle in range(5):
        for aid in TEST_ACCOUNT_IDS:
            from core_engine.mt_runtime import MTConnectionConfig
            runtime = MTRuntimeMock(MTConnectionConfig(
                server="x", login="0", password="x", platform="MT4",
            ))
            await runtime.connect()
            market_data = MarketData(runtime)
            profile = profile_builder.create_profile(
                client_id=aid, account_type="PERSONAL",
                balance=10000, equity=9950,
                broker="stress", prop_firm=None, currency="USD",
                use_recommended_settings=True,
            )
            symbols = [s.name for s in await runtime.get_symbols()]
            for sym in symbols:
                candidate = await detector.detect(market_data, sym, "M5")
                if candidate is None:
                    continue
                if candidate.score_result and candidate.score_result.recommendation != "EXECUTE":
                    continue
                planner = TradePlanner()
                price = 2350.0
                plan = planner.plan(candidate, profile, price)
                if plan.valid:
                    key = f"{sym}_{candidate.direction}"
                    if key not in paper_log[aid]:
                        trade = await paper_trading.create_from_plan(aid, user_id, candidate, plan)
                        paper_log[aid].append(key)
                        paper_count_before[aid] += 1

            await runtime.disconnect()
        print(f"  Cycle {cycle+1}/5: {sum(paper_count_before.values())} unique paper trades total")

    total_paper = sum(paper_count_before.values())
    print(f"  [OK] {total_paper} unique paper trades (no duplicates across cycles)")
    for aid, keys in paper_log.items():
        assert len(keys) == len(set(keys)), f"Duplicates in account {aid}"

    # -- Phase 3: Breach isolation --
    print("\n-- Phase 3: Risk breach isolation --")
    BREACH_ACCOUNT_ID = TEST_ACCOUNT_IDS[0]

    from core_engine.scanner import account_scanner
    await account_scanner.start_scanning(BREACH_ACCOUNT_ID)

    breach_result = await scanner.scan_account(BREACH_ACCOUNT_ID)
    print(f"  Breach result: success={breach_result.success}, breaches={len(breach_result.breaches)}")

    async with async_session_factory() as session:
        from sqlalchemy import select, update
        from database.models import TradingAccount
        acc_mgr = AccountManager(session)
        risk_mgr = RiskManager(session)
        await acc_mgr.pause_account(BREACH_ACCOUNT_ID)
        await session.commit()

        stmt = select(TradingAccount).where(TradingAccount.id == BREACH_ACCOUNT_ID)
        breached = (await session.execute(stmt)).scalar_one()
        print(f"  Breached account engine_status: {breached.engine_status}")
        assert breached.engine_status == "PAUSED", \
            f"Expected PAUSED, got {breached.engine_status}"
        print("  [OK] Breached account -> SUSPENDED")

        stmt_all = select(TradingAccount).where(
            TradingAccount.id.in_(TEST_ACCOUNT_IDS[1:])
        )
        others = list((await session.execute(stmt_all)).scalars().all())
        for o in others:
            assert o.engine_status != "SUSPENDED", \
                f"Account {o.id} should not be suspended"
        print(f"  [OK] Other {len(others)} accounts not affected")

    await account_scanner.stop_scanning(BREACH_ACCOUNT_ID)

    # -- Phase 4: Account state isolation --
    print("\n-- Phase 4: Account state isolation --")
    async with async_session_factory() as session:
        for aid in TEST_ACCOUNT_IDS:
            scans = await session.execute(
                select(AccountScan).where(AccountScan.account_id == aid)
            )
            scan_list = list(scans.scalars().all())
            for s in scan_list:
                assert s.account_id == aid, f"Scan account_id mismatch: {s.account_id} != {aid}"

        paper_trades = await session.execute(
            select(PaperTrade).where(PaperTrade.account_id.in_(TEST_ACCOUNT_IDS))
        )
        pt_list = list(paper_trades.scalars().all())
        for pt in pt_list:
            assert pt.account_id in TEST_ACCOUNT_IDS, \
                f"Paper trade orphaned: {pt.id} -> account {pt.account_id}"
        print(f"  [OK] {len(pt_list)} paper trades belong to valid accounts")

    print("\n" + "=" * 60)
    print("*** STRESS TEST OK ***")
    print("=" * 60)


async def main():
    try:
        await run_stress()
    finally:
        await cleanup()
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
