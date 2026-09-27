import sys, os
sys.path.insert(0, r"C:\Users\AGA GAMING\Desktop\test saas")

# Load env
env_path = os.path.join("config", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")

import asyncio
from datetime import datetime, timezone, timedelta
import random
random.seed(42)

from telegram_bot.api_client import telegram_application
from telegram_bot.ui.trade_messages import (
    format_entry_message,
    format_exit_message,
    format_performance_summary,
    format_license_info,
    format_open_trades,
    format_help,
)
from media.pro_chart import pro_entry_chart, pro_exit_chart, pro_running_chart, pro_perf_card

CHAT_ID = 7320801946

async def main():
    bot = telegram_application.app.bot

    print("1. Sending Entry Alert + Chart...")
    ohlc = []
    now = datetime.now(timezone.utc)
    price = 3368.0
    for i in range(40):
        t = now - timedelta(minutes=i * 5)
        open_p = price
        high = price + random.uniform(0.5, 2.0)
        low = price - random.uniform(0.5, 2.0)
        close = low + random.uniform(0.1, high - low)
        ohlc.append((t, open_p, high, low, close))
        price = close + random.uniform(-0.3, 0.3)

    entry_path = pro_entry_chart(
        trade_id="demo_entry_001",
        symbol="XAUUSD",
        direction="BUY",
        entry_price=3368.25,
        stop_loss=3361.10,
        take_profit=3386.20,
        reasons=["BOS + CHoCH", "Bullish FVG", "Liquidity Sweep", "Order Block",
                 "MSS", "Mitigation", "Discount Zone", "London Killzone"],
        ohlc_data=ohlc,
        session="London",
        killzone="London Killzone",
        score=96.0,
        confidence=88.0,
        rr=2.5,
        entry_time=now,
        market_structure="Bullish Structure",
        eq_price=3364.0,
        bos_levels=[3355.0],
        choch_levels=[3345.0],
        liquidity_sweeps=[3338.5],
        fvg_zones=[(3356.0, 3360.5)],
        order_blocks=[(3348.0, 3354.0, "bullish")],
        imbalances=[(3362.0, 3364.0)],
        swings=[
            (now - timedelta(minutes=55), 3335.0, "LL"),
            (now - timedelta(minutes=45), 3345.0, "HL"),
            (now - timedelta(minutes=35), 3338.0, "LL"),
            (now - timedelta(minutes=25), 3355.0, "HH"),
            (now - timedelta(minutes=15), 3348.0, "LH"),
        ],
        liquidity_levels=[(3335.0, "EQH"), (3342.0, "PDH"), (3328.0, "Asia Low")],
        stats={"Lot": "0.1", "Risk": "1%", "Spread": "0.8"},
    )

    entry_text = format_entry_message(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=3368.25,
        stop_loss=3361.10,
        take_profit=3386.20,
        score=96,
        confidence=88,
        risk_pct=0.5,
        rr=2.5,
        reasons=["BOS + CHoCH", "Bullish FVG", "Liquidity Sweep", "Order Block"],
        lot_size=0.1,
        session="London",
    )

    if entry_path and os.path.exists(entry_path):
        with open(entry_path, "rb") as f:
            await bot.send_photo(chat_id=CHAT_ID, photo=f, caption=entry_text)
        print("   Entry chart sent!")
    else:
        await bot.send_message(chat_id=CHAT_ID, text=entry_text)
        print("   Entry text sent (no chart)")

    await asyncio.sleep(1)

    print("2. Sending Exit Alert + Chart...")
    exit_path = pro_exit_chart(
        trade_id="demo_entry_001",
        symbol="XAUUSD",
        direction="BUY",
        entry_price=3368.25,
        stop_loss=3361.10,
        take_profit=3386.20,
        exit_price=3386.20,
        exit_reason="TP HIT",
        realized_pnl=179.50,
        realized_r=2.5,
        ohlc_data=ohlc,
        session="London",
        score=96.0,
        confidence=88.0,
        rr=2.5,
        entry_time=now,
        market_structure="Bullish Structure",
        mfe=22.5,
        mae=3.8,
        break_even_price=3368.25,
        reasons=["TP Hit", "Run your winners"],
        fvg_zones=[(3356.0, 3360.5)],
        order_blocks=[(3348.0, 3354.0, "bullish")],
        swings=[
            (now - timedelta(minutes=85), 3335.0, "LL"),
            (now - timedelta(minutes=75), 3345.0, "HL"),
        ],
        stats={"Lot": "0.1", "Fee": "$0.50"},
    )

    exit_text = format_exit_message(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=3368.25,
        exit_price=3386.20,
        exit_reason="TP_HIT",
        realized_pnl=179.50,
        realized_r=2.5,
        duration="3h 42m",
        mfe=22.5,
        mae=3.8,
    )

    if exit_path and os.path.exists(exit_path):
        with open(exit_path, "rb") as f:
            await bot.send_photo(chat_id=CHAT_ID, photo=f, caption=exit_text)
        print("   Exit chart sent!")
    else:
        await bot.send_message(chat_id=CHAT_ID, text=exit_text)
        print("   Exit text sent (no chart)")

    await asyncio.sleep(1)

    print("3. Sending Performance Card...")
    perf_card_path = pro_perf_card({
        'today_pnl': '+$179.50',
        'weekly_pnl': '+$847.20',
        'monthly_pnl': '+$3,241.80',
        'win_rate': '65.96%',
        'profit_factor': '2.41',
        'expectancy': '1.82R',
        'drawdown': '4.2%',
        'current_streak': '7 wins',
    })
    if perf_card_path and os.path.exists(perf_card_path):
        with open(perf_card_path, "rb") as f:
            await bot.send_photo(chat_id=CHAT_ID, photo=f, caption="📊 Performance Summary")
        print("   Performance card sent!")
    else:
        perf_text = format_performance_summary(
            total_trades=47, wins=31, losses=16, win_rate=65.96,
            net_pnl=2847.30, profit_factor=2.41, avg_r=1.82,
            best_symbol="XAUUSD", today_pnl=179.50,
        )
        await bot.send_message(chat_id=CHAT_ID, text=perf_text)
        print("   Performance text sent!")

    await asyncio.sleep(1)

    print("4. Sending Running Trade Chart...")
    running_path = pro_running_chart(
        trade_id="demo_entry_001",
        symbol="XAUUSD", direction="BUY",
        entry_price=3368.25, stop_loss=3361.10, take_profit=3386.20,
        ohlc_data=ohlc,
        session="London", score=96.0, confidence=88.0, rr=2.5,
        floating_pnl=85.0, current_price=3376.50,
        entry_time=now,
        stats={"RR": "1.2", "Lot": "0.1"},
    )
    if running_path and os.path.exists(running_path):
        with open(running_path, "rb") as f:
            running_text = "🔄 Trade Running\nXAUUSD BUY | Floating: +$85.00 | Current RR: 1.2"
            await bot.send_photo(chat_id=CHAT_ID, photo=f, caption=running_text)
        print("   Running chart sent!")
    else:
        await bot.send_message(chat_id=CHAT_ID, text="🔄 Trade Running — no chart available")
        print("   Running text sent (no chart)")

    await asyncio.sleep(1)

    print("4. Sending License Info...")
    lic_text = format_license_info(
        license_key="ICT-X7K2-M9P4-RT61",
        plan="Premium",
        status="ACTIVE",
        expires_at="2026-12-31",
        max_accounts=3,
        bound_accounts=1,
    )
    await bot.send_message(chat_id=CHAT_ID, text=lic_text)
    print("   License sent!")

    await asyncio.sleep(1)

    print("5. Sending Open Trades...")
    trades = [
        {"symbol": "XAUUSD", "direction": "BUY", "entry": 3368.25, "sl": 3361.10, "tp": 3386.20, "lots": 0.1, "profit": 2.4, "rr": 2.5, "duration": "3h 42m"},
        {"symbol": "GBPUSD", "direction": "SELL", "entry": 1.2940, "sl": 1.2980, "tp": 1.2860, "lots": 0.2, "profit": -1.8, "rr": 2.0, "duration": "1h 15m"},
    ]
    open_text = format_open_trades(trades)
    await bot.send_message(chat_id=CHAT_ID, text=open_text)
    print("   Open trades sent!")

    await asyncio.sleep(1)

    print("6. Sending Help...")
    help_text = format_help()
    await bot.send_message(chat_id=CHAT_ID, text=help_text)
    print("   Help sent!")

    print("\nDone! Check Telegram for all messages.")

if __name__ == "__main__":
    asyncio.run(main())
