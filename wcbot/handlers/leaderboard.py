from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.state_manager import StateManagerAgent
from wcbot.utils.formatting import format_leaderboard
from wcbot.models.leaderboard import LeaderboardTimeframe


async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state: StateManagerAgent = context.bot_data["state_manager"]
    entries = await state.get_leaderboard(top_n=50)
    await update.message.reply_markdown(format_leaderboard(entries))
