from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.state_manager import StateManagerAgent
from wcbot.utils.formatting import format_model_card


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state: StateManagerAgent = context.bot_data["state_manager"]
    user = update.effective_user
    await state.create_user(
        chat_id=user.id,
        username=user.username,
        first_name=user.first_name,
        language=user.language_code or "en",
    )

    engine = context.bot_data["prediction_engine"]
    card = await engine.get_model_card()

    await update.message.reply_markdown(
        f"⚽ *Welcome to ZT WC PredBot!*\n\n"
        f"AI-powered predictions for the 2026 World Cup.\n"
        f"Powered by a 5-model ensemble engine.\n\n"
        f"{format_model_card(card)}\n\n"
        f"Try `/predict Brazil vs Argentina` to start!"
    )
