from telegram import Update
from telegram.ext import ContextTypes

from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.utils.live_tournament import format_kickoff


async def fixtures_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    fixtures = await ingestion.fetch_world_cup_odds()
    if not fixtures:
        fixtures = await ingestion.fetch_world_cup_events()
    if not fixtures:
        await update.message.reply_markdown(
            "📅 *2026 World Cup Fixtures*\n\n"
            "The live FIFA World Cup fixture feed is unavailable right now. Try again shortly."
        )
        return

    lines = ["📅 *Next Confirmed World Cup Fixtures*", ""]
    for fixture in fixtures[:12]:
        lines.append(
            f"• *{fixture['home_team']} vs {fixture['away_team']}*\n"
            f"  {format_kickoff(fixture.get('commence_time', ''))}"
        )
        if fixture.get("bookmaker_count"):
            lines.append(
                f"  Market: {fixture['home_team']} {fixture.get('market_home_prob', 0):.0%} | "
                f"Draw {fixture.get('market_draw_prob', 0):.0%} | "
                f"{fixture['away_team']} {fixture.get('market_away_prob', 0):.0%}"
            )
    lines.extend(["", "Use `/predict <home> vs <away>` for a fixture forecast."])
    await update.message.reply_markdown("\n".join(lines))


async def results_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    results = [match for match in await ingestion.fetch_world_cup_scores() if match.get("status") == "completed"]
    if not results:
        await update.message.reply_markdown(
            "✅ *Recent World Cup Results*\n\nNo completed matches were returned by the live feed."
        )
        return

    lines = ["✅ *Recent World Cup Results*", ""]
    for match in results[:12]:
        lines.append(
            f"• *{match['home_team']} {match.get('home_score', '?')}–"
            f"{match.get('away_score', '?')} {match['away_team']}*\n"
            f"  {format_kickoff(match.get('commence_time', ''))}"
        )
    lines.extend(["", "Source: The Odds API FIFA World Cup score feed."])
    await update.message.reply_markdown("\n".join(lines))
