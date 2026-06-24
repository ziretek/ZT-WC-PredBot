from telegram import Update
from telegram.ext import ContextTypes
from wcbot.utils.formatting import format_insights


async def insights_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data["prediction_engine"]

    upsets = [
        {
            "home": "Uruguay", "away": "Brazil",
            "winner": "Uruguay", "confidence": 0.42,
            "reasoning": "Historical rivalry and home advantage in South American qualifiers.",
        },
        {
            "home": "Denmark", "away": "France",
            "winner": "Denmark", "confidence": 0.38,
            "reasoning": "Denmark's disciplined defense neutralizes France's attack.",
        },
        {
            "home": "Japan", "away": "Germany",
            "winner": "Draw", "confidence": 0.45,
            "reasoning": "Japan's quick transitions trouble Germany's high line.",
        },
    ]

    await update.message.reply_markdown(format_insights(upsets))
