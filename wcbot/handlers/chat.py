import re
import logging
from uuid import uuid4

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
)

from wcbot.agents.prediction_engine import (
    PredictionEngineAgent,
    MIN_CONFIDENCE_FOR_PREDICTION,
    MIN_MODELS_AGREEING,
)
from wcbot.agents.state_manager import StateManagerAgent
from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.handlers.tournament import is_round_of_32_request
from wcbot.models.prediction import Prediction
from wcbot.utils.formatting import format_prediction, format_tentative_prediction
from wcbot.utils.teams import normalize_team_name, unknown_team_message
from wcbot.data.teams import WORLD_CUP_TEAMS_2026, TEAM_CONTINENTS, QUALIFIED_COUNT

logger = logging.getLogger(__name__)

ASK_HOME, ASK_AWAY, ASK_FOLLOWUP, COMPARE_TEAM = range(4)

CANCEL_KEYBOARD = [["/cancel"]]


async def chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(
        "💬 *Chat Mode*\n\n"
        "I can help you with predictions conversationally.\n\n"
        "*Examples:*\n"
        "• \"Predict Brazil vs Argentina\"\n"
        "• \"Who will win the World Cup?\"\n"
        "• \"Compare France and England\"\n"
        "• \"Explain the model\"\n\n"
        "Send `/cancel` anytime to exit chat mode.\n\n"
        "What would you like to know?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_HOME


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    lower = text.lower()

    if is_round_of_32_request(text) or any(w in lower for w in ["who advanced", "teams in the round"]):
        return await handle_round_of_32(update, context)
    elif "compare" in lower:
        return await handle_compare_request(update, context, text)
    elif "predict" in lower or "vs" in lower:
        return await handle_predict_request(update, context, text)
    elif "win" in lower and ("world cup" in lower or "tournament" in lower):
        return await handle_simulation_request(update, context)
    elif lower.strip() in ("hello", "hi", "hey", "hello!", "hi!", "hey!") or \
         lower.startswith("hello ") or lower.startswith("hi ") or lower.startswith("hey "):
        await update.message.reply_markdown(
            "Hello! 👋 Want a World Cup prediction? Just say *\"Predict Brazil vs Argentina\"*"
        )
        return ASK_FOLLOWUP
    elif "help" in lower or "what can" in lower:
        await update.message.reply_markdown(
            "Ask me anything about the 2026 World Cup!\n\n"
            "• `Predict Brazil vs Argentina`\n"
            "• `Who wins the tournament?`\n"
            "• `Compare France vs England`\n"
            "• `Explain how you predict`"
        )
        return ASK_FOLLOWUP
    elif "model" in lower or "how" in lower:
        return await handle_model_explain(update, context)
    elif any(w in lower for w in ["which countr", "what countr", "which team", "what team",
                                   "list team", "list countr", "who is in", "who plays",
                                   "participat", "qualified team", "all team", "all countr"]):
        return await handle_teams_question(update, context)
    elif any(w in lower for w in ["list group", "show group", "group stand", "group table",
                                   "what are the group", "group a", "group b", "group stage"]):
        return await handle_list_groups(update, context)
    elif any(w in lower for w in ["round of 32", "round of thirty", "knockout stage",
                                   "who advanced", "next round", "ro32", "r32",
                                   "teams in the round"]):
        return await handle_round_of_32(update, context)
    elif any(w in lower for w in ["is ", "are ", "does ", "did ", "has "]) and \
         any(w in lower for w in ["qualif", "in the world cup", "participat", "play in",
                                   "competing", "in the tournament"]):
        return await handle_team_lookup(update, context, text)
    elif any(w in lower for w in ["who are you", "what are you", "tell me about yourself",
                                   "what is your name", "your name"]):
        await update.message.reply_markdown(
            "I'm *ZT WC PredBot* ⚽ — your AI assistant for the 2026 World Cup!\n\n"
            "I can predict matches using a 4-model ensemble (Elo, Poisson xG, Gradient Boosting, LLM), "
            "show group standings, list qualified teams, simulate the tournament, and answer your WC questions.\n\n"
            "Try `/predict Brazil vs Argentina` or just chat with me!"
        )
        return ASK_FOLLOWUP
    elif any(w in lower for w in ["where is", "where will", "where are", "which country",
                                   "host", "venue", "stadium", "location", "city"]):
        await update.message.reply_markdown(
            "The *2026 World Cup* is co-hosted by the **USA, Canada, and Mexico** — "
            "the first time 3 nations share hosting duties! Matches are played across 16 stadiums "
            "in cities like New York, Los Angeles, Mexico City, Toronto, and Vancouver.\n\n"
            "Use `/teams` to see all qualified nations, or `/predict <team> vs <team>` for predictions!"
        )
        return ASK_FOLLOWUP
    else:
        engine: PredictionEngineAgent = context.bot_data.get("prediction_engine")
        llm_answer = None
        if engine and engine.llm:
            llm_answer = await engine.llm.answer_question(text)
        if llm_answer:
            await update.message.reply_markdown(llm_answer)
        else:
            await update.message.reply_markdown(
                "I'm not sure what you mean. Try:\n"
                "• \"Predict Brazil vs Argentina\"\n"
                "• \"Who will win the World Cup?\"\n"
                "• \"Which countries are in the World Cup?\"\n"
                "• `/help` for commands"
            )
        return ASK_FOLLOWUP


async def handle_teams_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"🌍 *2026 World Cup — {QUALIFIED_COUNT} Qualified Teams*\n\n"
    for continent in ["CONCACAF", "CONMEBOL", "UEFA", "CAF", "AFC", "OFC"]:
        teams = sorted(t for t in WORLD_CUP_TEAMS_2026 if TEAM_CONTINENTS.get(t) == continent)
        label = {"CONCACAF": "North/Central America", "CONMEBOL": "South America",
                 "UEFA": "Europe", "CAF": "Africa", "AFC": "Asia", "OFC": "Oceania"}[continent]
        text += f"*{label}:* {', '.join(teams)}\n\n"
    text += "Use `/predict <team> vs <team>` to get AI predictions!"
    await update.message.reply_markdown(text)
    return ASK_FOLLOWUP


async def handle_list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ingestion: DataIngestionAgent = context.bot_data.get("data_ingestion")
    if not ingestion:
        await update.message.reply_markdown("Group data is not available.")
        return ASK_FOLLOWUP

    standings = await ingestion.fetch_standings()
    if not standings:
        await update.message.reply_markdown(
            "Live group standings require a `SPORTS_API_KEY` configured in `.env`.\n\n"
            "Without it, I can still predict matches — try `/predict Brazil vs Argentina`."
        )
        return ASK_FOLLOWUP

    groups = {}
    for entry in standings:
        groups.setdefault(entry["group"], []).append(entry)

    text = "📊 *2026 World Cup — Group Standings*\n\n"
    for g in sorted(groups.keys()):
        teams = sorted(groups[g], key=lambda t: (-t["points"], -t["goal_diff"]))
        text += f"*Group {g}:*\n"
        for t in teams:
            text += f"  {t['name']} — {t['points']}pts (GD {t['goal_diff']:+d})\n"
        text += "\n"

    text += "Use `/predict <home> vs <away>` for match predictions!"
    await update.message.reply_markdown(text)
    return ASK_FOLLOWUP


async def handle_round_of_32(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ingestion: DataIngestionAgent = context.bot_data.get("data_ingestion")
    if not ingestion:
        await update.message.reply_markdown(
            "Standings data not available yet. Try `/standings` for group tables."
        )
        return ASK_FOLLOWUP

    advancing = await ingestion.fetch_round_of_32()
    if not advancing:
        engine: PredictionEngineAgent = context.bot_data.get("prediction_engine")
        if engine and engine.llm:
            llm_answer = await engine.llm.answer_question("Which teams are in the round of 32 of the 2026 World Cup?")
            if llm_answer:
                await update.message.reply_markdown(llm_answer)
                return ASK_FOLLOWUP
        await update.message.reply_markdown(
            "Round of 32 standings require live group data from `SPORTS_API_KEY`.\n\n"
            "Try `/simulate` for a tournament outlook, or `/predict Brazil vs Argentina` "
            "for an individual match prediction."
        )
        return ASK_FOLLOWUP

    text = "🏆 *Round of 32 — Advancing Teams*\n\n"
    for entry in advancing:
        flag = {"Algeria": "🇩🇿", "Argentina": "🇦🇷", "Australia": "🇦🇺", "Austria": "🇦🇹",
                "Belgium": "🇧🇪", "Bosnia and Herzegovina": "🇧🇦", "Brazil": "🇧🇷", "Canada": "🇨🇦",
                "Cape Verde": "🇨🇻", "Colombia": "🇨🇴", "Croatia": "🇭🇷", "Curaçao": "🇨🇼",
                "Czech Republic": "🇨🇿", "DR Congo": "🇨🇩", "Ecuador": "🇪🇨",
                "Egypt": "🇪🇬", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "France": "🇫🇷",
                "Germany": "🇩🇪", "Ghana": "🇬🇭", "Haiti": "🇭🇹", "Iran": "🇮🇷",
                "Iraq": "🇮🇶", "Ivory Coast": "🇨🇮", "Japan": "🇯🇵", "Jordan": "🇯🇴",
                "Mexico": "🇲🇽", "Morocco": "🇲🇦", "Netherlands": "🇳🇱",
                "New Zealand": "🇳🇿", "Norway": "🇳🇴", "Panama": "🇵🇦",
                "Paraguay": "🇵🇾", "Portugal": "🇵🇹", "Qatar": "🇶🇦",
                "Saudi Arabia": "🇸🇦", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Senegal": "🇸🇳",
                "South Africa": "🇿🇦", "South Korea": "🇰🇷", "Spain": "🇪🇸",
                "Sweden": "🇸🇪", "Switzerland": "🇨🇭", "Tunisia": "🇹🇳",
                "Turkey": "🇹🇷", "United States": "🇺🇸", "Uruguay": "🇺🇾",
                "Uzbekistan": "🇺🇿"}.get(entry["name"], "")
        text += f"{flag} *{entry['group']}* — {entry['name']} ({entry['points']}pts, GD {entry['goal_diff']:+d})\n"

    text += "\nThe knockout stage begins now! Use `/predict <home> vs <away>` to get predictions."
    await update.message.reply_markdown(text)
    return ASK_FOLLOWUP


async def handle_team_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    words = text.lower().split()
    team_name = None
    for team in sorted(WORLD_CUP_TEAMS_2026, key=len, reverse=True):
        if team.lower() in text.lower():
            team_name = team
            break

    if team_name:
        continent = TEAM_CONTINENTS.get(team_name, "")
        label = {"CONCACAF": "North/Central America", "CONMEBOL": "South America",
                 "UEFA": "Europe", "CAF": "Africa", "AFC": "Asia", "OFC": "Oceania"}.get(continent, continent)
        await update.message.reply_markdown(
            f"✅ Yes, *{team_name}* is qualified for the 2026 World Cup! ({label})"
        )
    else:
        await update.message.reply_markdown(
            "❌ That team is not in the 2026 World Cup qualified list. "
            "Use `/teams` to see all qualified nations."
        )
    return ASK_FOLLOWUP


async def handle_predict_request(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    text = re.sub(r"^/predict\b", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^predict\b", "", text, flags=re.IGNORECASE).strip()

    if is_round_of_32_request(text):
        return await handle_round_of_32(update, context)

    if " vs " not in text:
        await update.message.reply_markdown(
            "Which match do you want me to predict? Say *\"Brazil vs Argentina\"*.\n\n"
            "For knockout qualification, say *\"round of 32\"*."
        )
        return ASK_HOME

    parts = re.split(r'\s+vs\s+', text, maxsplit=1)
    if len(parts) != 2:
        return ASK_HOME

    raw_home, raw_away = parts[0].strip(), parts[1].strip()
    home = normalize_team_name(raw_home)
    away = normalize_team_name(raw_away)
    if not home:
        await update.message.reply_markdown(unknown_team_message(raw_home))
        return ASK_FOLLOWUP
    if not away:
        await update.message.reply_markdown(unknown_team_message(raw_away))
        return ASK_FOLLOWUP
    if home == away:
        await update.message.reply_markdown("Choose two different teams.")
        return ASK_FOLLOWUP

    sent = await update.message.reply_markdown(f"🧠 Analyzing *{home} vs {away}*...")

    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    state: StateManagerAgent = context.bot_data["state_manager"]
    user = update.effective_user
    await state.create_user(
        chat_id=user.id,
        username=user.username,
        first_name=user.first_name,
        language=user.language_code or "en",
    )

    result = await engine.predict(home, away)

    if result.abstained:
        await sent.edit_text(
            format_tentative_prediction(
                result,
                home,
                away,
                MIN_MODELS_AGREEING,
                MIN_CONFIDENCE_FOR_PREDICTION,
            ),
            parse_mode="Markdown",
        )
        context.user_data["last_home"] = home
        context.user_data["last_away"] = away
        context.user_data["last_prediction"] = result
        return ASK_FOLLOWUP

    pred = Prediction(
        prediction_id=str(uuid4()),
        user_id=update.effective_user.id,
        match_id=f"{home.lower()}-{away.lower()}",
        home_team=home,
        away_team=away,
        predicted_home_score=result.home_score,
        predicted_away_score=result.away_score,
        predicted_winner=result.winner,
        confidence=result.confidence,
        model_version=result.model_version,
    )
    await state.save_prediction(update.effective_user.id, pred.match_id, pred)

    await sent.edit_text(format_prediction(result, home, away), parse_mode="Markdown")

    context.user_data["last_home"] = home
    context.user_data["last_away"] = away
    context.user_data["last_prediction"] = result

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Swap teams", callback_data="swap")],
        [InlineKeyboardButton("📊 Detailed comparison", callback_data="deep_dive")],
        [InlineKeyboardButton("🎲 Simulate tournament", callback_data="simulate")],
        [InlineKeyboardButton("❓ Ask something else", callback_data="new_question")],
    ])
    await update.message.reply_markdown(
        "What next?", reply_markup=keyboard
    )
    return ASK_FOLLOWUP


async def handle_simulation_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    await update.message.reply_markdown("🎲 Running 10,000 tournament simulations...")
    results = await engine.simulate_tournament(iterations=10000)

    from wcbot.utils.formatting import format_simulation
    lines = format_simulation(results)

    for chunk in [lines[i:i + 4000] for i in range(0, len(lines), 4000)]:
        await update.message.reply_markdown(chunk)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 Predict a match", callback_data="predict")],
        [InlineKeyboardButton("❓ Ask something else", callback_data="new_question")],
    ])
    await update.message.reply_markdown("What next?", reply_markup=keyboard)
    return ASK_FOLLOWUP


async def handle_compare_request(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    text = re.sub(r"^compare\b", "", text, flags=re.IGNORECASE).strip()
    if " vs " not in text:
        await update.message.reply_markdown(
            "Which two teams? Say *\"Compare France vs England\"*"
        )
        return ASK_HOME

    parts = re.split(r'\s+vs\s+', text, maxsplit=1)
    if len(parts) != 2:
        return ASK_HOME

    raw_t1, raw_t2 = parts[0].strip(), parts[1].strip()
    t1 = normalize_team_name(raw_t1)
    t2 = normalize_team_name(raw_t2)
    if not t1:
        await update.message.reply_markdown(unknown_team_message(raw_t1))
        return ASK_FOLLOWUP
    if not t2:
        await update.message.reply_markdown(unknown_team_message(raw_t2))
        return ASK_FOLLOWUP
    if t1 == t2:
        await update.message.reply_markdown("Choose two different teams.")
        return ASK_FOLLOWUP
    engine = context.bot_data["prediction_engine"]

    p1 = await engine.predict(t1, t2)
    p2 = await engine.predict(t2, t1)

    if p1.abstained and p2.abstained:
        msg = f"📊 *{t1} vs {t2} — Comparison*\n\n🤷 Both sides too close to call confidently."
    else:
        msg = (
            f"📊 *{t1} vs {t2} — Comparison*\n\n"
            f"*{t1} (home):* {p1.winner} {p1.home_score}-{p1.away_score} "
            f"(conf: {p1.confidence:.0%})\n"
            f"*{t2} (home):* {p2.winner} {p2.home_score}-{p2.away_score} "
            f"(conf: {p2.confidence:.0%})\n\n"
            f"*Key insights:*\n"
            f"• {p1.reasoning}\n"
        )
    await update.message.reply_markdown(msg)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Predict a match", callback_data="predict")],
        [InlineKeyboardButton("❓ New question", callback_data="new_question")],
    ])
    await update.message.reply_markdown("Anything else?", reply_markup=keyboard)
    return ASK_FOLLOWUP


async def handle_model_explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    card = await engine.get_model_card()

    await update.message.reply_markdown(
        "🧠 *How I Predict*\n\n"
        "I use a **4-model ensemble**:\n\n"
        "1. *Elo* — Rating system. Teams gain/lose points based on match results. "
        f"{card.get('elo_teams_tracked', 0)} teams tracked.\n"
        "2. *Poisson xG* — Expected goals based on attack/defense strength per team.\n"
        "3. *Gradient Boosting* — Feature-weighted scoring (Elo diff, xG diff, form).\n"
        "4. *LLM* — Language model reasoning (if API key is configured).\n\n"
        f"*Accuracy:* {card.get('accuracy', 0):.0%} | "
        f"*Ensemble:* Elo {card.get('model_weights', {}).get('elo', 0):.0%}, "
        f"Poisson {card.get('model_weights', {}).get('poisson', 0):.0%}, "
        f"GB {card.get('model_weights', {}).get('gb', 0):.0%}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 Predict a match", callback_data="predict")],
        [InlineKeyboardButton("❓ New question", callback_data="new_question")],
    ])
    await update.message.reply_markdown("Try a prediction?", reply_markup=keyboard)
    return ASK_FOLLOWUP


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "swap":
        home = context.user_data.get("last_away")
        away = context.user_data.get("last_home")
        if home and away:
            await query.edit_message_text(f"🔄 Swapping... analyzing *{home} vs {away}*")
            engine = context.bot_data["prediction_engine"]
            result = await engine.predict(home, away)
            await query.edit_message_text(
                format_prediction(result, home, away),
                parse_mode="Markdown",
            )
            context.user_data["last_home"] = home
            context.user_data["last_away"] = away
            context.user_data["last_prediction"] = result

    elif data == "deep_dive":
        home = context.user_data.get("last_home", "?")
        away = context.user_data.get("last_away", "?")
        engine = context.bot_data["prediction_engine"]
        result = await engine.predict(home, away)
        parts = [
            f"📊 *Deep Dive: {home} vs {away}*\n",
            "*Ensemble Breakdown:*",
        ]
        eb = result.ensemble_breakdown
        for name, model in [("Elo", eb.elo), ("Poisson xG", eb.poisson_xg),
                            ("Gradient Boosting", eb.gradient_boosting),
                            ("LLM", eb.llm_weighted)]:
            parts.append(
                f"▸ *{name}:* {model.get('winner', '?')} "
                f"({model.get('home_score', '?')}–{model.get('away_score', '?')}, "
                f"conf {model.get('confidence', 0):.0%})"
            )
        parts.extend([
            "",
            "*Top Factors:*",
        ])
        for f in result.key_factors[:5]:
            parts.append(f"• {f['factor'].replace('_', ' ').title()} ({f['impact']:.0%} impact)")
        parts.extend([
            "",
            f"*Reasoning:* {result.reasoning}",
        ])
        await query.edit_message_text("\n".join(parts), parse_mode="Markdown")

    elif data == "simulate":
        await query.edit_message_text("🎲 Running 10,000 simulations...")
        engine = context.bot_data["prediction_engine"]
        results = await engine.simulate_tournament(iterations=10000)
        from wcbot.utils.formatting import format_simulation
        await query.edit_message_text(format_simulation(results), parse_mode="Markdown")

    elif data == "predict":
        await query.edit_message_text(
            "Which match? Say *\"Predict Brazil vs Argentina\"*"
        )
        return ASK_HOME

    elif data == "new_question":
        await query.edit_message_text(
            "Sure! What would you like to know?\n"
            "• Predict a match\n"
            "• Tournament simulation\n"
            "• Compare teams\n"
            "• Explain the model"
        )
        return ASK_HOME

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Another match", callback_data="predict")],
        [InlineKeyboardButton("❓ New question", callback_data="new_question")],
    ])
    await query.message.reply_markdown("Anything else?", reply_markup=keyboard)
    return ASK_FOLLOWUP


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last_home = context.user_data.pop("last_home", None)
    last_away = context.user_data.pop("last_away", None)

    msg = "👋 *Chat mode ended.*\n\n"
    if last_home and last_away:
        msg += f"Last prediction: *{last_home} vs {last_away}*\n"
        msg += "Come back anytime to dive deeper.\n\n"
    msg += "Use `/chat` to start again."

    await update.message.reply_markdown(msg, reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(
        "No active chat to cancel.\n"
        "Start one with `/chat`"
    )


def get_chat_conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("chat", chat_start)],
        states={
            ASK_HOME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(handle_callback),
            ],
            ASK_FOLLOWUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(handle_callback),
            ],
            COMPARE_TEAM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_predict_request),
                CallbackQueryHandler(handle_callback),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="wcbot_chat",
        persistent=False,
    )
