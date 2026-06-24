from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.state_manager import StateManagerAgent


async def subscribe_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/subscribe "):].strip()
    if not text:
        await update.message.reply_markdown("Usage: `/subscribe Brazil`")
        return

    state: StateManagerAgent = context.bot_data["state_manager"]
    await state.add_subscription(update.effective_user.id, text)

    await update.message.reply_markdown(
        f"✅ You'll now receive alerts for *{text}* — lineups, predictions, and live scores."
    )


async def unsubscribe_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/unsubscribe "):].strip()
    if not text:
        await update.message.reply_markdown("Usage: `/unsubscribe Brazil`")
        return

    state: StateManagerAgent = context.bot_data["state_manager"]
    await state.remove_subscription(update.effective_user.id, text)

    await update.message.reply_markdown(f"❌ Unsubscribed from *{text}* alerts.")
