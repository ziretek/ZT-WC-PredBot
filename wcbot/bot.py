import logging
import os

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import BotCommand

from wcbot.config import Config
from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.agents.state_manager import StateManagerAgent
from wcbot.realtime import RealtimeEngine
from wcbot.handlers import (
    start_handler,
    predict_handler,
    predictions_handler,
    leaderboard_handler,
    standings_handler,
    teams_handler,
    match_handler,
    simulate_handler,
    model_handler,
    insights_handler,
    subscribe_handler,
    unsubscribe_handler,
    feedback_handler,
    settings_handler,
    help_handler,
    track_handler,
    rtstatus_handler,
    value_handler,
    injuries_handler,
    round32_handler,
    winner_handler,
    tournament_handler,
    get_chat_conversation_handler,
    handle_message,
    cancel_global,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, Config.LOG_LEVEL),
)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    ingestion = DataIngestionAgent()
    engine = PredictionEngineAgent()
    state = StateManagerAgent()
    realtime = RealtimeEngine(app, ingestion, state, engine)

    app.bot_data["data_ingestion"] = ingestion
    app.bot_data["prediction_engine"] = engine
    app.bot_data["state_manager"] = state
    app.bot_data["realtime"] = realtime

    logger.info("Data dir: %s", Config.DATA_DIR)
    logger.info("State DB: %s", Config.STATE_DB_PATH)
    logger.info("Sports API: %s", "enabled" if Config.SPORTS_API_KEY else "disabled")
    logger.info("Odds API: %s", "enabled" if Config.ODDS_API_KEY else "disabled")
    logger.info("LLM reasoning: %s", "enabled" if Config.OPENAI_API_KEY else "disabled")

    if Config.SPORTS_API_KEY:
        await engine.pre_train(ingestion)
        await realtime.start()
        logger.info("Realtime engine + pre-training complete")
    elif Config.ODDS_API_KEY:
        await realtime.start()
        logger.info("Realtime engine started (odds only)")
    else:
        logger.info("Realtime engine disabled (no API keys — predictions use built-in data)")

    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Start the bot and show model status"),
            BotCommand("predict", "Predict a match or ask for round of 32"),
            BotCommand("round32", "Round of 32 outlook"),
            BotCommand("winner", "World Cup winner forecast"),
            BotCommand("simulate", "Tournament simulation"),
            BotCommand("teams", "Supported teams"),
            BotCommand("standings", "Group standings if live data is available"),
            BotCommand("value", "Compare model vs market odds"),
            BotCommand("chat", "Conversational mode"),
            BotCommand("help", "Show commands"),
        ])
    except Exception as e:
        logger.warning("Failed to update Telegram command menu: %s", e)


async def post_shutdown(app: Application):
    realtime = app.bot_data.get("realtime")
    ingestion = app.bot_data.get("data_ingestion")
    engine = app.bot_data.get("prediction_engine")
    state = app.bot_data.get("state_manager")

    if realtime:
        await realtime.stop()
    if ingestion:
        await ingestion.close()
    if engine:
        await engine.close()
    if state:
        state.close()
    logger.info("Shutdown cleanup complete")


def build_app() -> Application:
    Config.validate()
    app = (
        Application.builder()
        .token(Config.TELEGRAM_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("predict", predict_handler))
    app.add_handler(CommandHandler("predictions", predictions_handler))
    app.add_handler(CommandHandler("leaderboard", leaderboard_handler))
    app.add_handler(CommandHandler("standings", standings_handler))
    app.add_handler(CommandHandler("teams", teams_handler))
    app.add_handler(CommandHandler("match", match_handler))
    app.add_handler(CommandHandler("simulate", simulate_handler))
    app.add_handler(CommandHandler("tournament", tournament_handler))
    app.add_handler(CommandHandler("round32", round32_handler))
    app.add_handler(CommandHandler("winner", winner_handler))
    app.add_handler(CommandHandler("champion", winner_handler))
    app.add_handler(CommandHandler("model", model_handler))
    app.add_handler(CommandHandler("insights", insights_handler))
    app.add_handler(CommandHandler("subscribe", subscribe_handler))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_handler))
    app.add_handler(CommandHandler("feedback", feedback_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("track", track_handler))
    app.add_handler(CommandHandler("rtstatus", rtstatus_handler))
    app.add_handler(CommandHandler("value", value_handler))
    app.add_handler(CommandHandler("injuries", injuries_handler))
    app.add_handler(get_chat_conversation_handler())
    # Conversation state is intentionally in-memory. This fallback keeps plain
    # match requests working after a Render restart clears an active /chat.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("cancel", cancel_global))
    app.add_error_handler(error_handler)

    return app


async def error_handler(update, context):
    logger.error(f"Unhandled error: {context.error}", exc_info=context.error)
    if update and update.effective_message:
        await update.effective_message.reply_markdown(
            "⚠️ Something went wrong. Please try again."
        )


def main():
    app = build_app()

    webhook_url = Config.WEBHOOK_URL
    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
    if not webhook_url and render_host:
        webhook_url = f"https://{render_host}"
        logger.info(f"Detected Render: {webhook_url}")

    if webhook_url:
        full_webhook = f"{webhook_url}/{Config.TELEGRAM_TOKEN}"
        logger.info(f"Webhook mode on port {Config.PORT}")
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", Config.PORT)),
            url_path=Config.TELEGRAM_TOKEN,
            webhook_url=full_webhook,
        )
    else:
        logger.info("Polling mode")
        app.run_polling()


if __name__ == "__main__":
    main()
