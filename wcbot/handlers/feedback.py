from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.agents.state_manager import StateManagerAgent


async def feedback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split()
    if len(parts) < 3:
        await update.message.reply_markdown("Usage: `/feedback <prediction_id> y/n`")
        return

    pred_id = parts[1]
    correct = parts[2].lower() in ("y", "yes", "correct", "1", "true")

    state: StateManagerAgent = context.bot_data["state_manager"]
    prediction = await state.get_prediction(pred_id)
    if not prediction or prediction.user_id != update.effective_user.id:
        await update.message.reply_markdown(
            "Couldn't find that prediction ID in your history. Check `/predictions`."
        )
        return

    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    engine.log_feedback(pred_id, correct, prediction.confidence)

    await update.message.reply_markdown(
        "✅ Feedback recorded. This helps improve future predictions."
    )
