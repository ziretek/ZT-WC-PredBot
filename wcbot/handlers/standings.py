from telegram import Update
from telegram.ext import ContextTypes
async def standings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(
        "📊 *2026 World Cup Standings*\n\n"
        "The configured live provider supplies verified fixtures, scores and betting markets, "
        "but not official group tables. I will not fabricate standings.\n\n"
        "Use `/results`, `/fixtures`, or `/round32` for verified tournament data."
    )
