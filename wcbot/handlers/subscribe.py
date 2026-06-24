from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.state_manager import StateManagerAgent
from wcbot.utils.teams import normalize_team_name, unknown_team_message


async def subscribe_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/subscribe "):].strip()
    if not text:
        await update.message.reply_markdown("Usage: `/subscribe Brazil`")
        return

    team = normalize_team_name(text)
    if not team:
        await update.message.reply_markdown(unknown_team_message(text))
        return

    user = update.effective_user
    state: StateManagerAgent = context.bot_data["state_manager"]
    await state.create_user(
        chat_id=user.id,
        username=user.username,
        first_name=user.first_name,
        language=user.language_code or "en",
    )
    await state.add_subscription(user.id, team)

    await update.message.reply_markdown(
        f"✅ You'll now receive alerts for *{team}* — lineups, predictions, and live scores."
    )


async def unsubscribe_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/unsubscribe "):].strip()
    if not text:
        await update.message.reply_markdown("Usage: `/unsubscribe Brazil`")
        return

    team = normalize_team_name(text)
    if not team:
        await update.message.reply_markdown(unknown_team_message(text))
        return

    state: StateManagerAgent = context.bot_data["state_manager"]
    await state.remove_subscription(update.effective_user.id, team)

    await update.message.reply_markdown(f"❌ Unsubscribed from *{team}* alerts.")
