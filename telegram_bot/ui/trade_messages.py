from __future__ import annotations

from typing import List, Optional


def format_entry_message(
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    score: float = 0,
    confidence: float = 0,
    risk_pct: float = 0,
    rr: float = 0,
    reasons: Optional[List[str]] = None,
    session: str = "",
    lot_size: float = 0,
) -> str:
    icon = "🟢" if direction == "BUY" else "🔴"
    pips = abs(entry_price - stop_loss) if entry_price and stop_loss else 0
    pips_str = f"{pips:.1f}" if pips > 0 else "—"

    lines = [
        "🔒 [PRV LOG] — NEW EXECUTION",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"{icon} {direction} {symbol} | {session or '—'}",
        f"📊 Score: {score:.0f}% | Confidence: {confidence:.0f}%",
        "",
        "🔍 WHY WE ENTERED (Technical Confluences):",
    ]
    if reasons:
        for i, r in enumerate(reasons[:4], 1):
            prefix = "└─" if i == len(reasons[:4]) else "├─"
            lines.append(f"{prefix} {i}. {r}")
    lines.append("")
    lines.append("📍 Trade Levels:")
    lines.append(f"├─ Entry Price : {entry_price:.2f}")
    lines.append(f"├─ Stop Loss   : {stop_loss:.2f} ({pips_str} pips)")
    lines.append(f"├─ Target (TP) : {take_profit:.2f} ({rr:.1f}R)")
    lines.append(f"└─ Risk / Size : {risk_pct:.1f}% | {lot_size:.2f} Lots")
    return "\n".join(lines)


def format_exit_message(
    symbol: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    exit_reason: str,
    realized_pnl: float,
    realized_r: float,
    duration: Optional[str] = None,
    mfe: Optional[float] = None,
    mae: Optional[float] = None,
    partial_pnl: Optional[float] = None,
    be_activated: bool = False,
    entry_reasons: Optional[List[str]] = None,
    exit_reasons: Optional[List[str]] = None,
) -> str:
    is_win = realized_pnl >= 0
    is_tp = "TP" in exit_reason or "tp" in exit_reason
    is_sl = "SL" in exit_reason or "sl" in exit_reason

    if is_win and is_tp:
        header = "🎉 [PRV LOG] — TRADE CLOSED (WIN)"
        icon = "🟢"
        result = "TAKE PROFIT HIT 🎯"
    elif is_sl:
        header = "🛑 [PRV LOG] — TRADE CLOSED (LOSS)"
        icon = "🔴"
        result = "STOP LOSS HIT ❌"
    else:
        header = "ℹ️ [PRV LOG] — TRADE CLOSED"
        icon = "🟢" if is_win else "🔴"
        result = exit_reason

    pnl_icon = "💰" if is_win else "🔻"
    pnl_prefix = "+" if is_win else ""
    rr_label = f"+{realized_r:.2f}R" if realized_r > 0 else f"{realized_r:.2f}R"

    lines = [
        header,
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"{icon} {symbol} — {result}",
        f"{pnl_icon} PnL: {pnl_prefix}${realized_pnl:.2f} ({rr_label})",
    ]
    if duration:
        lines[-1] += f" | Duration: {duration}"

    if is_win and exit_reasons:
        lines.append("")
        lines.append("✅ WHY IT WON (Success Analysis):")
        for i, r in enumerate(exit_reasons[:3], 1):
            prefix = "└─" if i == len(exit_reasons[:3]) else "├─"
            lines.append(f"{prefix} {r}")

    if is_sl and exit_reasons:
        lines.append("")
        lines.append("🔍 WHY IT LOST (Technical Breakdown / Post-Mortem):")
        for i, r in enumerate(exit_reasons[:3], 1):
            prefix = "└─" if i == len(exit_reasons[:3]) else "├─"
            lines.append(f"{prefix} ⚠️ {r}")

    lines.append("")
    lines.append("📈 Execution Metrics:")
    lines.append(f"├─ MFE (Max Potential) : +{mfe:.2f}R" if mfe else "├─ MFE : —")
    lines.append(f"├─ MAE (Max Drawdown)  : -{mae:.2f}R" if mae else "├─ MAE : —")
    if is_tp and is_win:
        lines.append("└─ Exit Status         : Closed at Target 🎯")
    elif is_sl:
        lines.append("└─ Exit Status         : Stopped Out ❌")
    else:
        lines.append(f"└─ Exit                : {exit_reason}")

    if partial_pnl:
        lines.append("")
        lines.append(f"📌 Partial Close : +${partial_pnl:.2f}")

    if be_activated:
        lines.append("📌 Breakeven      : Activated ✅")

    if is_sl:
        lines.append("")
        lines.append("💡 Action: Logged to database for Strategy Backtest Review.")

    return "\n".join(lines)


def format_performance_summary(
    total_trades: int,
    wins: int,
    losses: int,
    win_rate: float,
    net_pnl: float,
    profit_factor: float,
    avg_r: float,
    best_symbol: str = "",
    today_pnl: float = 0,
) -> str:
    lines = [
        "📊 [PRV LOG] — PERFORMANCE SUMMARY",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📈 Total Trades : {total_trades}",
        f"✅ Wins         : {wins}",
        f"❌ Losses       : {losses}",
        f"📊 Win Rate     : {win_rate:.1f}%",
        "",
        f"💰 Net P&L      : {'+' if net_pnl >= 0 else ''}${net_pnl:.2f}",
        f"📅 Today        : {'+' if today_pnl >= 0 else ''}${today_pnl:.2f}",
        f"📊 Profit Factor: {profit_factor:.2f}",
        f"📐 Avg R        : {avg_r:.2f}R",
    ]
    if best_symbol:
        lines.append(f"🏆 Best Symbol  : {best_symbol}")
    return "\n".join(lines)


def format_license_info(
    license_key: str,
    plan: str,
    status: str,
    expires_at: Optional[str] = None,
    max_accounts: int = 1,
    bound_accounts: int = 0,
) -> str:
    status_icon = {"active": "✅", "inactive": "⏸️", "expired": "❌", "suspended": "🚫"}
    icon = status_icon.get(status, "❓")
    lines = [
        "🔑 [PRV LOG] — LICENSE",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"Key    : `{license_key}`",
        f"Plan   : {plan}",
        f"Status : {icon} {status.upper()}",
        f"Accts  : {bound_accounts}/{max_accounts}",
    ]
    if expires_at:
        lines.append(f"Expires: {expires_at}")
    return "\n".join(lines)


def format_open_trades(trades: list) -> str:
    if not trades:
        return "📭 No open trades"
    lines = ["📈 [PRV LOG] — OPEN POSITIONS", ""]
    for i, t in enumerate(trades, 1):
        icon = "🟢" if t.get("direction") == "BUY" else "🔴"
        pnl = t.get("unrealized_pnl", 0)
        pnl_str = f"{'+' if pnl >= 0 else ''}${pnl:.2f}" if pnl else "—"
        lines.append(f"{i}. {icon} {t.get('symbol', '?')}")
        lines.append(f"   Entry: {t.get('entry_price', '?')} | P&L: {pnl_str}")
    return "\n".join(lines)


def format_help() -> str:
    return """🤖 ICT EA Pro — Commands

/start      — Main menu
/status     — Bot status
/performance— Performance
/license    — License info
/history    — Recent trades
/open       — Open positions
/help       — This message"""
