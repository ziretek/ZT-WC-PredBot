import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")
    SPORTS_API_KEY: str = os.getenv("SPORTS_API_KEY", "")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    PORT: int = int(os.getenv("PORT", os.getenv("PORT", "8443")))
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")
    STATE_DB_PATH: str = os.getenv("STATE_DB_PATH", os.path.join(DATA_DIR, "state.db"))
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_URL: str = os.getenv("OPENAI_API_URL", "https://api.deepseek.com/v1/chat/completions")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    TOURNAMENT_YEAR: int = 2026
    ENSEMBLE_DISAGREEMENT_THRESHOLD: float = 0.30
    LEADERBOARD_TOP_N: int = 50

    @classmethod
    def validate(cls):
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN is required")
        os.makedirs(cls.DATA_DIR, exist_ok=True)
