from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.data_ingestion import DataIngestionAgent


async def injuries_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/injuries "):].strip()
    if not text:
        await update.message.reply_markdown("Usage: `/injuries Brazil`")
        return

    team = text
    await update.message.reply_markdown(f"🩻 Checking injuries for *{team}*...")

    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    injuries = await ingestion.fetch_injuries(team)

    if injuries:
        msg = f"🩻 *Injuries — {team}*\n\n"
        for inj in injuries[:10]:
            status = "❌" if inj["type"] == "injury" else "⚠️"
            ret = f" (returns: {inj['return_date']})" if inj["return_date"] != "unknown" else ""
            msg += f"{status} {inj['player']}{ret}\n"
        if len(injuries) > 10:
            msg += f"\n...and {len(injuries) - 10} more."
    else:
        msg = (
            f"✅ No injury data available for *{team}*.\n\n"
            "Injury data requires `SPORTS_API_KEY` and Sportmonks coverage. "
            "Teams may have no reported injuries, or the data source may not have this team."
        )

    await update.message.reply_markdown(msg)
