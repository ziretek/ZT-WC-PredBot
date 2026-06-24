from telegram import Update
from telegram.ext import ContextTypes
from wcbot.utils.formatting import format_help


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(format_help())
