from telegram import Update
from telegram.ext import ContextTypes
from wcbot.utils.formatting import format_team_list


async def teams_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teams = [
        {"name": "Brazil", "rating": 95},
        {"name": "Argentina", "rating": 93},
        {"name": "France", "rating": 94},
        {"name": "England", "rating": 90},
        {"name": "Germany", "rating": 88},
        {"name": "Spain", "rating": 89},
        {"name": "Portugal", "rating": 87},
        {"name": "Netherlands", "rating": 86},
        {"name": "Belgium", "rating": 84},
        {"name": "Italy", "rating": 85},
        {"name": "Croatia", "rating": 82},
        {"name": "Uruguay", "rating": 81},
        {"name": "Colombia", "rating": 79},
        {"name": "Denmark", "rating": 78},
        {"name": "Switzerland", "rating": 76},
        {"name": "Japan", "rating": 75},
        {"name": "Morocco", "rating": 74},
        {"name": "Senegal", "rating": 73},
        {"name": "USA", "rating": 72},
        {"name": "Mexico", "rating": 71},
    ]
    await update.message.reply_markdown(format_team_list(teams))
