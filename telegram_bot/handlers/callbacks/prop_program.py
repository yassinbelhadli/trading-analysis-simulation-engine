from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.data.prop_firms import get_prop_program
from telegram_bot.ui.keyboards.account_sizes import account_sizes_keyboard
from telegram_bot.services.setup import get_setup


async def handle_prop_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    program_id = query.data.replace("PROP_PROGRAM:", "")
    prop_id = context.user_data.get("prop_firm")

    program = get_prop_program(prop_id, program_id)

    if program is None:
        await query.edit_message_text("❌ Invalid program.")
        return

    setup = get_setup(context)

    setup["prop_firm"]["program_id"] = program["id"]
    setup["prop_firm"]["program_name"] = program["name"]
    setup["prop_firm"]["challenge_type"] = program["challenge_type"]
    setup["prop_firm"]["account_type"] = program["account_type"]

    rules = program.get("rules", {})

    setup["risk"]["daily_loss"] = rules.get("daily_loss")
    setup["risk"]["max_loss"] = rules.get("max_loss")
    setup["risk"]["profit_target"] = rules.get("profit_target_phase_1")
    setup["risk"]["min_trades"] = rules.get("min_trading_days")

    context.user_data["prop_program"] = program["id"]
    context.user_data["prop_program_name"] = program["name"]

    await query.edit_message_text(
        text=(
            "✅ <b>Program Selected</b>\n\n"
            f"{program['name']}\n\n"
            f"<b>Challenge:</b> {program['challenge_type']}\n"
            f"<b>Type:</b> {program['account_type']}\n\n"
            "💰 <b>Choose account size</b>"
        ),
        parse_mode="HTML",
        reply_markup=account_sizes_keyboard(program["account_sizes"]),
    )