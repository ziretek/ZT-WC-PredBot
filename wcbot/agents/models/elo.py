import json
import os
import logging
from math import pow
from typing import Optional

from wcbot.config import Config

logger = logging.getLogger(__name__)

K_FACTOR = 32
INITIAL_RATING = 1500
HOME_ADVANTAGE = 70


class EloModel:
    def __init__(self, persist_path: Optional[str] = None):
        self.persist_path = persist_path or os.path.join(Config.DATA_DIR, "elo_ratings.json")
        self.ratings: dict[str, float] = self._load()
        self.match_count = 0

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + pow(10, (rating_b - rating_a) / 400.0))

    def predict_match(self, home_team: str, away_team: str) -> dict:
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)
        home_effective = home_rating + HOME_ADVANTAGE

        exp_home = self.expected_score(home_effective, away_rating)
        exp_away = 1.0 - exp_home
        exp_draw = 0.0

        if exp_home > 0.6:
            exp_draw = 0.22
            exp_home -= exp_draw * 0.6
            exp_away -= exp_draw * 0.4
        elif exp_away > 0.6:
            exp_draw = 0.22
            exp_home -= exp_draw * 0.4
            exp_away -= exp_draw * 0.6
        else:
            exp_draw = 0.26
            exp_home -= exp_draw * 0.5
            exp_away -= exp_draw * 0.5

        winner = home_team if exp_home > exp_away else away_team
        if abs(exp_home - exp_away) < 0.08:
            winner = "Draw"

        home_lambda = max(0.3, (home_effective / 1600.0) * 1.6)
        away_lambda = max(0.2, (away_rating / 1600.0) * 1.1)
        prob_home_goals = self._poisson_pmf(home_lambda, 6)
        prob_away_goals = self._poisson_pmf(away_lambda, 6)

        max_prob = 0
        home_score = 1
        away_score = 1
        for hs in range(5):
            for as_ in range(5):
                prob = prob_home_goals[hs] * prob_away_goals[as_]
                if hs == as_ and winner != "Draw":
                    continue
                if hs > as_ and winner != home_team:
                    continue
                if as_ > hs and winner != away_team:
                    continue
                if prob > max_prob:
                    max_prob = prob
                    home_score = hs
                    away_score = as_

        confidence = max(exp_home, exp_away, exp_draw)
        if winner == "Draw":
            confidence *= 0.5
        confidence = min(round(confidence, 2), 0.88)

        return {
            "winner": winner,
            "home_score": home_score,
            "away_score": away_score,
            "confidence": confidence,
            "home_rating": round(home_rating, 1),
            "away_rating": round(away_rating, 1),
            "home_win_prob": round(exp_home, 3),
            "draw_prob": round(exp_draw, 3),
            "away_win_prob": round(exp_away, 3),
        }

    def update_ratings(self, home: str, away: str, home_score: int, away_score: int):
        home_rating = self.get_rating(home)
        away_rating = self.get_rating(away)
        home_effective = home_rating + HOME_ADVANTAGE

        exp_home = self.expected_score(home_effective, away_rating)
        exp_away = 1.0 - exp_home

        if home_score > away_score:
            actual_home, actual_away = 1.0, 0.0
        elif home_score < away_score:
            actual_home, actual_away = 0.0, 1.0
        else:
            actual_home, actual_away = 0.5, 0.5

        home_new = home_rating + K_FACTOR * (actual_home - exp_home)
        away_new = away_rating + K_FACTOR * (actual_away - exp_away)

        home_goals_exp = (home_effective / away_rating) * 1.5
        away_goals_exp = (away_rating / home_effective) * 1.0

        goal_diff_weight = 0.3
        home_new += goal_diff_weight * (home_score - home_goals_exp)
        away_new += goal_diff_weight * (away_score - away_goals_exp)

        self.ratings[home] = round(home_new, 1)
        self.ratings[away] = round(away_new, 1)
        self.match_count += 1
        self._save()

    def get_rating(self, team: str) -> float:
        return self.ratings.get(team, INITIAL_RATING)

    def get_rankings(self, top_n: int = 30) -> list:
        sorted_teams = sorted(self.ratings.items(), key=lambda x: -x[1])
        return [{"name": t, "rating": r} for t, r in sorted_teams[:top_n]]

    @staticmethod
    def _default_ratings() -> dict:
        return {
            "Brazil": 1850, "Argentina": 1820, "France": 1800,
            "England": 1780, "Spain": 1760, "Germany": 1750,
            "Portugal": 1740, "Netherlands": 1730, "Italy": 1720,
            "Belgium": 1700, "Croatia": 1680, "Uruguay": 1660,
            "Colombia": 1640, "Denmark": 1630, "Switzerland": 1610,
            "Japan": 1600, "Morocco": 1590, "Senegal": 1580,
            "USA": 1570, "Mexico": 1560, "South Korea": 1550,
            "Australia": 1540, "Poland": 1570, "Serbia": 1560,
            "Iran": 1530, "Ivory Coast": 1520, "Ghana": 1510,
            "Saudi Arabia": 1480, "Cameroon": 1490, "Tunisia": 1500,
            "Canada": 1510, "Ecuador": 1530, "Costa Rica": 1470,
            "Wales": 1550, "Scotland": 1520, "Austria": 1540,
            "Sweden": 1530, "Norway": 1520, "Turkey": 1550,
            "Czech Republic": 1510, "Ukraine": 1500, "Russia": 1490,
        }

    def _load(self) -> dict:
        defaults = self._default_ratings()
        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path) as f:
                    saved = json.load(f)
                defaults.update(saved)
                return defaults
            except Exception as e:
                logger.warning(f"Failed to load Elo ratings: {e}")
        return defaults

    def _save(self):
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        with open(self.persist_path, "w") as f:
            json.dump(self.ratings, f, indent=2)

    def _poisson_pmf(self, lam: float, max_k: int) -> list:
        prob = [0.0] * (max_k + 1)
        if lam <= 0:
            prob[0] = 1.0
            return prob
        factorial = 1
        for k in range(max_k + 1):
            prob[k] = pow(lam, k) * pow(2.71828, -lam) / factorial
            factorial *= (k + 1)
        total = sum(prob)
        return [p / total for p in prob]
