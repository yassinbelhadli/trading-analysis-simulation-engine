"""Enable real trading on FTMO demo account."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import async_session_factory
from database.models import TradingAccount, RiskProfile
from sqlalchemy import select

async def main():
    async with async_session_factory() as s:
        acc = (await s.execute(
            select(TradingAccount).where(TradingAccount.active == True)
        )).scalar_one()
        print(f"Before: real_trading_enabled={acc.real_trading_enabled} trade_mode={acc.trade_mode}")
        acc.real_trading_enabled = True
        acc.trade_mode = "MODERATE"
        # Also create risk profile if missing
        rp = (await s.execute(
            select(RiskProfile).where(RiskProfile.account_id == acc.id)
        )).scalar_one_or_none()
        if not rp:
            rp = RiskProfile(account_id=acc.id, mode="balanced", max_risk_trade=2.0)
            s.add(rp)
            print("Created RiskProfile")
        else:
            print(f"RiskProfile exists: mode={rp.mode}")
        await s.commit()
        print(f"After: real_trading_enabled={acc.real_trading_enabled} trade_mode={acc.trade_mode}")

asyncio.run(main())
