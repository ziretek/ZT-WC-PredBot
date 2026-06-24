import logging

from telegram.ext import Application, CommandHandler

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

    await realtime.start()
    logger.info("Realtime engine auto-started")


def build_app() -> Application:
    Config.validate()
    app = Application.builder().token(Config.TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("predict", predict_handler))
    app.add_handler(CommandHandler("predictions", predictions_handler))
    app.add_handler(CommandHandler("leaderboard", leaderboard_handler))
    app.add_handler(CommandHandler("standings", standings_handler))
    app.add_handler(CommandHandler("teams", teams_handler))
    app.add_handler(CommandHandler("match", match_handler))
    app.add_handler(CommandHandler("simulate", simulate_handler))
    app.add_handler(CommandHandler("model", model_handler))
    app.add_handler(CommandHandler("insights", insights_handler))
    app.add_handler(CommandHandler("subscribe", subscribe_handler))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_handler))
    app.add_handler(CommandHandler("feedback", feedback_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("track", track_handler))
    app.add_handler(CommandHandler("rtstatus", rtstatus_handler))
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

    if Config.WEBHOOK_URL:
        logger.info(f"Starting webhook mode on port {Config.PORT}")
        app.run_webhook(
            listen="0.0.0.0",
            port=Config.PORT,
            url_path=Config.TELEGRAM_TOKEN,
            webhook_url=f"{Config.WEBHOOK_URL}/{Config.TELEGRAM_TOKEN}",
        )
    else:
        logger.info("Starting polling mode")
        app.run_polling()


if __name__ == "__main__":
    main()
