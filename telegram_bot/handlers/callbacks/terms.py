from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.data.brokers import get_broker, get_broker_servers
from telegram_bot.data.prop_firms import get_prop_firm, get_prop_servers
from telegram_bot.services.setup import get_setup
from telegram_bot.ui.keyboards.platform import platform_keyboard
from telegram_bot.ui.keyboards.servers import servers_keyboard


async def _proceed_after_platform(query, context, platform):
    setup = get_setup(context)
    setup["platform"]["type"] = platform
    context.user_data["platform"] = platform

    servers = []
    account_type = context.user_data.get("account_type")
    if account_type == "FUNDED":
        prop_id = context.user_data.get("prop_firm")
        servers = get_prop_servers(prop_id, platform)
    elif account_type == "PERSONAL":
        broker_id = context.user_data.get("broker")
        servers = get_broker_servers(broker_id, platform)

    if servers:
        await query.edit_message_text(
            text=(
                f"✅ <b>{platform}</b>\n\n"
                "🖥️ <b>Select your server</b>"
            ),
            parse_mode="HTML",
            reply_markup=servers_keyboard(servers),
        )
        return

    example = context.user_data.get("mt_server_example", "ICMarketsSC-MT5")

    context.user_data["waiting_for"] = "MT_SERVER"
    await query.edit_message_text(
        text=(
            f"✅ <b>{platform}</b>\n\n"
            f"🔐 <b>{platform} Connection</b>\n\n"
            f"Please enter your {platform} server name.\n\n"
            f"Example:\n"
            f"{example}"
        ),
        parse_mode="HTML",
    )


async def handle_terms_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data["terms_accepted"] = True

    account_type = context.user_data.get("account_type")
    available_platforms = []

    if account_type == "FUNDED":
        firm = get_prop_firm(context.user_data.get("prop_firm"))
        if firm:
            available_platforms = firm.get("platforms", [])
    elif account_type == "PERSONAL":
        # MT4 is no longer supported; only offer MT5
        available_platforms = ["MT5"]

    if len(available_platforms) == 1:
        await _proceed_after_platform(query, context, available_platforms[0])
        return

    await query.edit_message_text(
        text=(
            "🖥️ <b>Select your trading platform</b>\n\n"
            "Choose the platform used by your account."
        ),
        parse_mode="HTML",
        reply_markup=platform_keyboard(),
    )