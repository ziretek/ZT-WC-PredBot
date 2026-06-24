import logging
from datetime import datetime
from typing import Optional

from wcbot.models.user import User, UserSettings
from wcbot.models.prediction import Prediction
from wcbot.models.leaderboard import LeaderboardEntry, LeaderboardTimeframe

logger = logging.getLogger(__name__)


class StateManagerAgent:
    def __init__(self):
        self._users: dict[int, User] = {}
        self._predictions: dict[str, Prediction] = {}
        self._subscriptions: dict[int, set] = {}

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
        return self._users[chat_id]

    async def get_user(self, chat_id: int) -> Optional[User]:
        return self._users.get(chat_id)

    async def update_user_activity(self, chat_id: int):
        user = await self.get_user(chat_id)
        if user:
            user.last_active = datetime.utcnow()

    async def save_prediction(self, user_id: int, match_id: str, prediction: Prediction):
        self._predictions[prediction.prediction_id] = prediction
        user = await self.get_user(user_id)
        if user:
            user.total_predictions += 1

    async def get_prediction_history(self, user_id: int, limit: int = 50) -> list:
        return [
            p for p in self._predictions.values()
            if p.user_id == user_id
        ][-limit:]

    async def resolve_match(self, match_id: str, home_score: int, away_score: int,
                             home_team: Optional[str] = None, away_team: Optional[str] = None,
                             prediction_engine=None):
        for pred in self._predictions.values():
            if pred.match_id != match_id:
                continue
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
            if user and pred.points_awarded:
                user.points += pred.points_awarded
                if pred.was_correct:
                    user.correct_predictions += 1

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
        return await self.update_leaderboard(timeframe)

    async def get_user_stats(self, user_id: int) -> dict:
        user = await self.get_user(user_id)
        if not user:
            return {}
        return {
            "total_predictions": user.total_predictions,
            "correct_predictions": user.correct_predictions,
            "accuracy": user.accuracy,
            "points": user.points,
            "rank": 1,
        }

    async def add_subscription(self, user_id: int, team: str):
        if user_id not in self._subscriptions:
            self._subscriptions[user_id] = set()
        self._subscriptions[user_id].add(team)

    async def remove_subscription(self, user_id: int, team: str):
        if user_id in self._subscriptions:
            self._subscriptions[user_id].discard(team)

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
