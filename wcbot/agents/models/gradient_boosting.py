import json
import os
import logging
from math import exp

from wcbot.config import Config

logger = logging.getLogger(__name__)


class GradientBoostingModel:
    def __init__(self, persist_path: Optional[str] = None):
        self.persist_path = persist_path or os.path.join(Config.DATA_DIR, "gb_weights.json")
        self.weights: dict = self._load()
        if not self.weights:
            self.weights = self._init_weights()
        self.n_estimators = 50

    def predict_match(self, home_team: str, away_team: str,
                      elo_pred: dict, poisson_pred: dict,
                      features: dict) -> dict:
        feature_vector = self._extract_features(home_team, away_team, elo_pred, poisson_pred, features)
        score = self._score_features(feature_vector)
        prob_home = 1.0 / (1.0 + exp(-score))

        prob_draw = 0.22 + 0.08 * (1.0 - abs(prob_home - 0.5) * 2)
        if prob_home > 0.7:
            prob_home = prob_home * (1.0 - prob_draw / 2)
            prob_away = 1.0 - prob_home - prob_draw
        elif prob_home < 0.3:
            prob_away = prob_home
            prob_home = 1.0 - prob_away - prob_draw
        else:
            prob_away = 1.0 - prob_home - prob_draw

        prob_home = max(0.05, min(0.90, prob_home))
        prob_away = max(0.05, min(0.90, prob_away))
        prob_draw = 1.0 - prob_home - prob_away

        winner = home_team if prob_home > prob_away else away_team
        if prob_draw > max(prob_home, prob_away):
            winner = "Draw"

        raw_home = elo_pred.get("home_score", 1) * 0.4 + poisson_pred.get("expected_home_goals", 1.5) * 0.6
        raw_away = elo_pred.get("away_score", 1) * 0.4 + poisson_pred.get("expected_away_goals", 1.0) * 0.6
        home_score = max(0, round(raw_home))
        away_score = max(0, round(raw_away))
        if home_score == away_score:
            if winner == home_team:
                home_score += 1
            elif winner == away_team:
                away_score += 1

        confidence = max(prob_home, prob_away, prob_draw)
        confidence = min(round(confidence, 2), 0.90)

        return {
            "winner": winner,
            "home_score": home_score,
            "away_score": away_score,
            "confidence": confidence,
            "home_win_prob": round(prob_home, 3),
            "draw_prob": round(prob_draw, 3),
            "away_win_prob": round(prob_away, 3),
            "gb_score": round(score, 3),
            "top_features": self._top_features(feature_vector),
        }

    def _extract_features(self, home: str, away: str,
                          elo_pred: dict, poisson_pred: dict,
                          features: dict) -> dict:
        return {
            "elo_diff": elo_pred.get("home_rating", 1500) - elo_pred.get("away_rating", 1500),
            "elo_home_win_prob": elo_pred.get("home_win_prob", 0.5),
            "poisson_home_win_prob": poisson_pred.get("home_win_prob", 0.5),
            "expected_home_goals": poisson_pred.get("expected_home_goals", 1.5),
            "expected_away_goals": poisson_pred.get("expected_away_goals", 1.0),
            "home_attack": poisson_pred.get("home_attack", 1.0),
            "away_defense": poisson_pred.get("away_defense", 1.0),
            "rest_days_diff": features.get("rest_days_diff", 0),
            "home_advantage": 1.0,
        }

    def _score_features(self, fv: dict) -> float:
        score = self.weights["bias"]
        score += fv["elo_diff"] / 400.0 * self.weights["elo_diff"]
        score += fv["elo_home_win_prob"] * self.weights["elo_home_win_prob"]
        score += fv["poisson_home_win_prob"] * self.weights["poisson_home_win_prob"]
        score += (fv["expected_home_goals"] - fv["expected_away_goals"]) * self.weights["goal_diff"]
        score += fv["home_attack"] * self.weights["home_attack"]
        score += fv["rest_days_diff"] * self.weights["rest_days"]
        score += fv["home_advantage"] * self.weights["home_advantage"]
        return score

    def _top_features(self, fv: dict) -> list:
        impacts = []
        for k, v in fv.items():
            w = self.weights.get(k, 0)
            impacts.append({"feature": k, "impact": round(abs(v * w), 3)})
        impacts.sort(key=lambda x: -x["impact"])
        return impacts[:3]

    def update_weights(self, features: list, actual_home_win: bool, learning_rate: float = 0.01):
        score = self._score_features(features[-1]) if features else 0
        error = (1.0 if actual_home_win else 0.0) - (1.0 / (1.0 + exp(-score)))
        for k in self.weights:
            if k == "bias":
                self.weights[k] += learning_rate * error
            elif k != "goal_diff" and k != "home_advantage":
                if features:
                    self.weights[k] += learning_rate * error * features[-1].get(k, 0)
        self._save()

    def _init_weights(self) -> dict:
        return {
            "bias": 0.0,
            "elo_diff": 0.45,
            "elo_home_win_prob": 0.30,
            "poisson_home_win_prob": 0.25,
            "goal_diff": 0.35,
            "home_attack": 0.20,
            "rest_days": 0.10,
            "home_advantage": 0.15,
        }

    def _load(self) -> dict:
        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load GB weights: {e}")
        return {}

    def _save(self):
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        with open(self.persist_path, "w") as f:
            json.dump(self.weights, f, indent=2)
