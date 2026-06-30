import re

from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.utils.teams import normalize_team_name, unknown_team_message


def _form_bar(elo_rating: float, baseline: float = 1500) -> str:
    diff = (elo_rating - baseline) / 200.0
    diff = max(-1, min(1, diff))
    bars = int(abs(diff) * 8)
    if diff > 0:
        return "🟢" * bars + "⬜" * (8 - bars) + " (hot)"
    elif diff < 0:
        return "🔴" * bars + "⬜" * (8 - bars) + " (cold)"
    return "⬜" * 8 + " (neutral)"


async def match_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/match "):].strip()
    if not text or "vs" not in text:
        await update.message.reply_markdown("Usage: `/match Brazil vs Argentina`")
        return

    parts = re.split(r'\s+vs\s+', text, maxsplit=1)
    if len(parts) != 2:
        return

    raw_home, raw_away = parts[0].strip(), parts[1].strip()
    home = normalize_team_name(raw_home)
    away = normalize_team_name(raw_away)
    if not home:
        await update.message.reply_markdown(unknown_team_message(raw_home))
        return
    if not away:
        await update.message.reply_markdown(unknown_team_message(raw_away))
        return
    if home == away:
        await update.message.reply_markdown("Choose two different teams.")
        return

    await update.message.reply_markdown(f"📊 Gathering dossier for *{home} vs {away}*...")

    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]

    h2h = await ingestion.fetch_head2head(home, away)
    prediction = await engine.predict(home, away)

    home_rating = engine.elo.get_rating(home)
    away_rating = engine.elo.get_rating(away)

    if prediction.abstained:
        verdict = (
            f"• Lean: *{prediction.winner}*\n"
            f"• Score: {prediction.home_score}–{prediction.away_score}\n"
            f"• Confidence: {prediction.confidence:.0%}\n"
            "• Status: ⚠️ Low-confidence prediction"
        )
    else:
        verdict = (
            f"• Winner: *{prediction.winner}*\n"
            f"• Score: {prediction.home_score}–{prediction.away_score}\n"
            f"• Confidence: {prediction.confidence:.0%}\n"
            f"• Model: `{prediction.model_version}`"
        )

    msg = (
        f"📊 *{home} vs {away} — Match Dossier*\n\n"
        f"*Elo Ratings:*\n"
        f"• {home}: {home_rating:.0f}\n"
        f"  Form: {_form_bar(home_rating)}\n"
        f"• {away}: {away_rating:.0f}\n"
        f"  Form: {_form_bar(away_rating)}\n\n"
        f"*Head-to-Head:*\n"
        f"• {home}: {h2h.get('team1_wins', 0)} wins\n"
        f"• {away}: {h2h.get('team2_wins', 0)} wins\n"
        f"• Draws: {h2h.get('draws', 0)}\n\n"
        f"*AI Verdict:*\n{verdict}\n"
    )

    msg += f"\n*Analysis:*\n{prediction.reasoning}"

    msg += f"\n\nUse `/value {home} vs {away}` to compare against market odds."
    await update.message.reply_markdown(msg)
