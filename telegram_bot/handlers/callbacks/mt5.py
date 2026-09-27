from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.data.brokers import get_broker
from telegram_bot.data.prop_firms import get_prop_firm
from telegram_bot.locales.translator import tr
from telegram_bot.ui.keyboards.terms import terms_keyboard


async def handle_mt5_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    account_type = context.user_data.get("account_type")
    example_server = "ICMarketsSC-MT5"

    if account_type == "PERSONAL":
        broker = get_broker(context.user_data.get("broker"))
        if broker:
            example_server = broker.get("server_example", example_server)

    elif account_type == "FUNDED":
        prop = get_prop_firm(context.user_data.get("prop_firm"))
        if prop:
            example_server = prop.get("server_example", example_server)

    context.user_data["mt_server_example"] = example_server

    await query.edit_message_text(
        text=(
            f"{tr(context, 'terms_title')}\n\n"
            f"{tr(context, 'terms_body')}"
        ),
        parse_mode="HTML",
        reply_markup=terms_keyboard(),
    )