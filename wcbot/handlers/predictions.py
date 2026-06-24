from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.state_manager import StateManagerAgent
from wcbot.utils.formatting import format_prediction_history


async def predictions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state: StateManagerAgent = context.bot_data["state_manager"]
    user = update.effective_user
    predictions = await state.get_prediction_history(user.id, limit=50)
    name = user.first_name or user.username or "User"
    await update.message.reply_markdown(format_prediction_history(predictions, name))
