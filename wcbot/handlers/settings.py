from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.state_manager import StateManagerAgent
from wcbot.utils.formatting import format_settings


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state: StateManagerAgent = context.bot_data["state_manager"]
    user = await state.get_user(update.effective_user.id)
    if not user:
        await update.message.reply_markdown("Please /start first.")
        return

    await update.message.reply_markdown(format_settings(user.settings))
