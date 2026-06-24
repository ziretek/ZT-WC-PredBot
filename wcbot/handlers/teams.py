from telegram import Update
from telegram.ext import ContextTypes
from wcbot.data.teams import WORLD_CUP_TEAMS_2026, TEAM_CONTINENTS, QUALIFIED_COUNT


async def teams_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"🌍 *2026 World Cup — {QUALIFIED_COUNT} Qualified Teams*\n\n"
    for continent in ["CONCACAF", "CONMEBOL", "UEFA", "CAF", "AFC", "OFC"]:
        teams = sorted(t for t in WORLD_CUP_TEAMS_2026 if TEAM_CONTINENTS.get(t) == continent)
        label = {"CONCACAF": "North/Central America", "CONMEBOL": "South America",
                 "UEFA": "Europe", "CAF": "Africa", "AFC": "Asia", "OFC": "Oceania"}[continent]
        text += f"*{label}:* {', '.join(teams)}\n\n"
    text += f"Use `/predict <home> vs <away>` to get AI predictions!"
    await update.message.reply_markdown(text)
