import json
import logging
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from wcbot.config import Config
from wcbot.models.user import User, UserSettings
from wcbot.models.prediction import Prediction
from wcbot.models.leaderboard import LeaderboardEntry, LeaderboardTimeframe

logger = logging.getLogger(__name__)


class StateManagerAgent:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.STATE_DB_PATH
        self._users: dict[int, User] = {}
        self._predictions: dict[str, Prediction] = {}
        self._subscriptions: dict[int, set[str]] = {}
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
        self._load_state()

    async def create_user(self, chat_id: int, username: Optional[str], first_name: Optional[str],
                          language: str = "en") -> User:
        if chat_id not in self._users:
            self._users[chat_id] = User(
                chat_id=chat_id,
                username=username,
                first_name=first_name,
                language_code=language,
            )
            logger.info(f"Created user {chat_id}")
        else:
            user = self._users[chat_id]
            user.username = username
            user.first_name = first_name
            user.language_code = language
            user.last_active = datetime.utcnow()

        self._persist_user(self._users[chat_id])
        return self._users[chat_id]

    async def get_user(self, chat_id: int) -> Optional[User]:
        return self._users.get(chat_id)

    async def update_user_activity(self, chat_id: int):
        user = await self.get_user(chat_id)
        if user:
            user.last_active = datetime.utcnow()
            self._persist_user(user)

    async def save_prediction(self, user_id: int, match_id: str, prediction: Prediction):
        self._predictions[prediction.prediction_id] = prediction
        user = await self.get_user(user_id)
        if not user:
            user = User(chat_id=user_id, username=None, first_name=None)
            self._users[user_id] = user
        user.total_predictions += 1
        self._persist_user(user)
        self._persist_prediction(prediction)

    async def get_prediction_history(self, user_id: int, limit: int = 50) -> list:
        predictions = [
            p for p in self._predictions.values()
            if p.user_id == user_id
        ]
        predictions.sort(key=lambda p: p.created_at)
        return predictions[-limit:]

    async def resolve_match(self, match_id: str, home_score: int, away_score: int,
                             home_team: Optional[str] = None, away_team: Optional[str] = None,
                             prediction_engine=None):
        for pred in self._predictions.values():
            if pred.match_id != match_id:
                continue

            old_points = pred.points_awarded or 0
            old_correct = 1 if pred.was_correct else 0

            pred.actual_home_score = home_score
            pred.actual_away_score = away_score
            pred.was_correct = (
                pred.predicted_home_score == home_score
                and pred.predicted_away_score == away_score
            )
            pred.points_awarded = self._calculate_points(
                pred.predicted_home_score, pred.predicted_away_score,
                home_score, away_score,
            )

            user = await self.get_user(pred.user_id)
            if user:
                user.points += pred.points_awarded - old_points
                user.correct_predictions += (1 if pred.was_correct else 0) - old_correct
                self._persist_user(user)

            self._persist_prediction(pred)

            if prediction_engine:
                prediction_engine.log_feedback(pred.prediction_id, bool(pred.was_correct), pred.confidence)

        if home_team and away_team and prediction_engine:
            prediction_engine.resolve_match(home_team, away_team, home_score, away_score)

    async def update_leaderboard(self, timeframe: LeaderboardTimeframe = LeaderboardTimeframe.ALL) -> list:
        sorted_users = sorted(
            self._users.values(),
            key=lambda u: (-u.points, -u.total_predictions, u.created_at),
        )
        return [
            LeaderboardEntry(
                rank=i + 1,
                username=u.username,
                first_name=u.first_name,
                points=u.points,
                total_predictions=u.total_predictions,
                correct_predictions=u.correct_predictions,
                accuracy=u.accuracy,
            )
            for i, u in enumerate(sorted_users[:50])
        ]

    async def get_leaderboard(self, top_n: int = 50, timeframe: LeaderboardTimeframe = LeaderboardTimeframe.ALL) -> list:
        entries = await self.update_leaderboard(timeframe)
        return entries[:top_n]

    async def get_user_stats(self, user_id: int) -> dict:
        user = await self.get_user(user_id)
        if not user:
            return {}

        ranked_users = sorted(
            self._users.values(),
            key=lambda u: (-u.points, -u.total_predictions, u.created_at),
        )
        rank = next((i + 1 for i, ranked in enumerate(ranked_users) if ranked.chat_id == user_id), 1)
        return {
            "total_predictions": user.total_predictions,
            "correct_predictions": user.correct_predictions,
            "accuracy": user.accuracy,
            "points": user.points,
            "rank": rank,
        }

    async def add_subscription(self, user_id: int, team: str):
        if user_id not in self._subscriptions:
            self._subscriptions[user_id] = set()
        self._subscriptions[user_id].add(team)
        self._persist_subscription(user_id, team)

    async def remove_subscription(self, user_id: int, team: str):
        if user_id in self._subscriptions:
            self._subscriptions[user_id].discard(team)
        self._delete_subscription(user_id, team)

    async def get_team_subscribers(self, team: str) -> list:
        return [
            uid for uid, teams in self._subscriptions.items()
            if team in teams
        ]

    def _calculate_points(self, pred_h: int, pred_a: int, actual_h: int, actual_a: int) -> int:
        if pred_h == actual_h and pred_a == actual_a:
            return 5
        pred_outcome = "home" if pred_h > pred_a else "away" if pred_a > pred_h else "draw"
        actual_outcome = "home" if actual_h > actual_a else "away" if actual_a > actual_h else "draw"
        if pred_outcome == actual_outcome:
            return 3
        if abs(pred_h - pred_a) == abs(actual_h - actual_a):
            return 2
        return -1

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _init_db(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language_code TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_active TEXT NOT NULL,
                settings_json TEXT NOT NULL,
                total_predictions INTEGER NOT NULL DEFAULT 0,
                correct_predictions INTEGER NOT NULL DEFAULT 0,
                points INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                match_id TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                predicted_home_score INTEGER NOT NULL,
                predicted_away_score INTEGER NOT NULL,
                predicted_winner TEXT NOT NULL,
                confidence REAL NOT NULL,
                model_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                actual_home_score INTEGER,
                actual_away_score INTEGER,
                points_awarded INTEGER,
                was_correct INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(chat_id)
            );

            CREATE INDEX IF NOT EXISTS idx_predictions_user_created
                ON predictions(user_id, created_at);

            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER NOT NULL,
                team TEXT NOT NULL,
                PRIMARY KEY(user_id, team),
                FOREIGN KEY(user_id) REFERENCES users(chat_id)
            );
            """
        )
        self._conn.commit()

    def _load_state(self):
        assert self._conn is not None

        for row in self._conn.execute(
            """
            SELECT chat_id, username, first_name, language_code, created_at, last_active,
                   settings_json, total_predictions, correct_predictions, points
            FROM users
            """
        ):
            settings_data = json.loads(row[6] or "{}")
            self._users[row[0]] = User(
                chat_id=row[0],
                username=row[1],
                first_name=row[2],
                language_code=row[3],
                created_at=self._parse_datetime(row[4]),
                last_active=self._parse_datetime(row[5]),
                settings=UserSettings(**settings_data),
                total_predictions=row[7],
                correct_predictions=row[8],
                points=row[9],
            )

        for row in self._conn.execute(
            """
            SELECT prediction_id, user_id, match_id, home_team, away_team,
                   predicted_home_score, predicted_away_score, predicted_winner,
                   confidence, model_version, created_at, actual_home_score,
                   actual_away_score, points_awarded, was_correct
            FROM predictions
            ORDER BY created_at
            """
        ):
            self._predictions[row[0]] = Prediction(
                prediction_id=row[0],
                user_id=row[1],
                match_id=row[2],
                home_team=row[3],
                away_team=row[4],
                predicted_home_score=row[5],
                predicted_away_score=row[6],
                predicted_winner=row[7],
                confidence=row[8],
                model_version=row[9],
                created_at=self._parse_datetime(row[10]),
                actual_home_score=row[11],
                actual_away_score=row[12],
                points_awarded=row[13],
                was_correct=None if row[14] is None else bool(row[14]),
            )

        for user_id, team in self._conn.execute("SELECT user_id, team FROM subscriptions"):
            self._subscriptions.setdefault(user_id, set()).add(team)

        logger.info(
            "Loaded state: %s users, %s predictions, %s subscriptions",
            len(self._users),
            len(self._predictions),
            sum(len(v) for v in self._subscriptions.values()),
        )

    def _persist_user(self, user: User):
        assert self._conn is not None
        self._conn.execute(
            """
            INSERT INTO users (
                chat_id, username, first_name, language_code, created_at, last_active,
                settings_json, total_predictions, correct_predictions, points
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                language_code=excluded.language_code,
                last_active=excluded.last_active,
                settings_json=excluded.settings_json,
                total_predictions=excluded.total_predictions,
                correct_predictions=excluded.correct_predictions,
                points=excluded.points
            """,
            (
                user.chat_id,
                user.username,
                user.first_name,
                user.language_code,
                user.created_at.isoformat(),
                user.last_active.isoformat(),
                json.dumps(asdict(user.settings)),
                user.total_predictions,
                user.correct_predictions,
                user.points,
            ),
        )
        self._conn.commit()

    def _persist_prediction(self, prediction: Prediction):
        assert self._conn is not None
        self._conn.execute(
            """
            INSERT INTO predictions (
                prediction_id, user_id, match_id, home_team, away_team,
                predicted_home_score, predicted_away_score, predicted_winner,
                confidence, model_version, created_at, actual_home_score,
                actual_away_score, points_awarded, was_correct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(prediction_id) DO UPDATE SET
                actual_home_score=excluded.actual_home_score,
                actual_away_score=excluded.actual_away_score,
                points_awarded=excluded.points_awarded,
                was_correct=excluded.was_correct
            """,
            (
                prediction.prediction_id,
                prediction.user_id,
                prediction.match_id,
                prediction.home_team,
                prediction.away_team,
                prediction.predicted_home_score,
                prediction.predicted_away_score,
                prediction.predicted_winner,
                prediction.confidence,
                prediction.model_version,
                prediction.created_at.isoformat(),
                prediction.actual_home_score,
                prediction.actual_away_score,
                prediction.points_awarded,
                None if prediction.was_correct is None else int(prediction.was_correct),
            ),
        )
        self._conn.commit()

    def _persist_subscription(self, user_id: int, team: str):
        assert self._conn is not None
        self._conn.execute(
            "INSERT OR IGNORE INTO subscriptions (user_id, team) VALUES (?, ?)",
            (user_id, team),
        )
        self._conn.commit()

    def _delete_subscription(self, user_id: int, team: str):
        assert self._conn is not None
        self._conn.execute(
            "DELETE FROM subscriptions WHERE user_id = ? AND team = ?",
            (user_id, team),
        )
        self._conn.commit()

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.utcnow()
