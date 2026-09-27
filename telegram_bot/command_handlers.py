from __future__ import annotations

from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import UserRepository, AccountRepository, LicenseRepository
from core_engine.engine_manager import engine_manager
from core_engine.engine_runner import engine_runner
from core_engine.mt_runtime import create_mt_runtime, MTConnectionConfig
from core_engine.execution.execution_guard import ExecutionGuard
from config.settings import ALLOW_REAL_TRADING, DEMO_ONLY
from telegram_bot.locales.translator import tr


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = await _resolve_user_id(update)
    if not user_id:
        await update.message.reply_text("Account not found. Use /start first.")
        return

    async with async_session_factory() as session:
        repo = AccountRepository(session)
        accounts = await repo.get_active_by_user_id(user_id)

    if not accounts:
        await update.message.reply_text("No active accounts found.")
        return

    lines = ["<b>📊 Engine Status</b>\n"]
    for acc in accounts:
        status = engine_manager.get_status(acc.id)
        running = engine_runner.is_running(acc.id)
        lines.append(
            f"<b>{acc.broker or 'Account'}</b> ({acc.platform})\n"
            f"  Status: {acc.engine_status}\n"
            f"  Engine: {'🟢 Running' if running else '🔴 Stopped'}\n"
            f"  Balance: ${acc.balance_snapshot or 0:.2f}\n"
            f"  Equity: ${acc.equity_snapshot or 0:.2f}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = await _resolve_user_id(update)
    if not user_id:
        await update.message.reply_text("Account not found.")
        return

    async with async_session_factory() as session:
        from core_engine.account_manager import AccountManager
        mgr = AccountManager(session)
        accounts = await mgr.get_active_accounts(user_id)
        for acc in accounts:
            await mgr.pause_account(acc.id)
            engine_manager.pause(acc.id)
        await session.commit()

    await update.message.reply_text("⏸️ Trading paused for all accounts.")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = await _resolve_user_id(update)
    if not user_id:
        await update.message.reply_text("Account not found.")
        return

    async with async_session_factory() as session:
        from core_engine.account_manager import AccountManager
        mgr = AccountManager(session)
        accounts = await mgr.get_all_accounts(user_id)
        for acc in accounts:
            if acc.engine_status == "PAUSED":
                await mgr.resume_account(acc.id)
                engine_manager.resume(acc.id)
        await session.commit()

    await update.message.reply_text("▶️ Trading resumed for all paused accounts.")


async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = await _resolve_user_id(update)
    if not user_id:
        await update.message.reply_text("Account not found.")
        return

    async with async_session_factory() as session:
        repo = AccountRepository(session)
        accounts = await repo.get_by_user_id(user_id)

    if not accounts:
        await update.message.reply_text("No accounts found.")
        return

    lines = ["<b>👤 Your Accounts</b>\n"]
    for i, acc in enumerate(accounts, 1):
        lines.append(
            f"{i}. <b>{acc.broker or 'Broker'}</b>\n"
            f"   Platform: {acc.platform} | Server: {acc.server or '-'}\n"
            f"   Type: {acc.account_type} | Size: ${acc.account_size or 0:,.0f}\n"
            f"   Status: {acc.engine_status} | {'✅ Active' if acc.active else '❌ Inactive'}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def guard_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = await _resolve_user_id(update)
    if not user_id:
        await update.message.reply_text(tr(context, "guard_not_found"))
        return

    async with async_session_factory() as session:
        repo = AccountRepository(session)
        accounts = await repo.get_active_by_user_id(user_id)

    if not accounts:
        await update.message.reply_text(tr(context, "guard_no_accounts"))
        return

    lines = [f"{tr(context, 'guard_title')}\n"]
    for acc in accounts:
        label = acc.broker or acc.platform or "Account"
        lines.append(f"\n<b>{label}</b> ({acc.platform})")

        eng_st = engine_manager.get_status(acc.id)
        running = engine_runner.is_running(acc.id)
        engine_icon = tr(context, "guard_pass") if running else tr(context, "guard_fail")
        uptime = eng_st.uptime_seconds
        uptime_str = f"{int(uptime//3600)}h{int((uptime%3600)//60)}m" if uptime else "-"
        lines.append(f"  {tr(context, 'guard_engine')}: {engine_icon} ({uptime_str})")

        lic_icon = tr(context, "guard_fail")
        async with async_session_factory() as session:
            lic_repo = LicenseRepository(session)
            lic = await lic_repo.get_by_id(acc.license_id) if acc.license_id else None
            if lic and lic.status == "active":
                lic_icon = tr(context, "guard_pass")
        lines.append(f"  {tr(context, 'guard_license')}: {lic_icon}")

        acc_icon = tr(context, "guard_pass") if acc.active else tr(context, "guard_fail")
        lines.append(f"  {tr(context, 'guard_account')}: {acc_icon}")

        rt_icon = tr(context, "guard_fail")
        if ALLOW_REAL_TRADING and acc.real_trading_enabled:
            rt_icon = tr(context, "guard_pass")
        lines.append(f"  {tr(context, 'guard_real_trading')}: {rt_icon}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def _resolve_user_id(update: Update) -> Optional[str]:
    telegram_id = update.effective_user.id
    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(telegram_id)
        if user:
            return user.id
    return None
