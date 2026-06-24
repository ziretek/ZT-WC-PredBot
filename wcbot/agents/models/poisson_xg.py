import json
import os
import logging
from math import exp, pow, factorial

from wcbot.config import Config

logger = logging.getLogger(__name__)

AVG_HOME_GOALS = 1.53
AVG_AWAY_GOALS = 1.15


class PoissonXGModel:
    def __init__(self, persist_path: Optional[str] = None):
        self.persist_path = persist_path or os.path.join(Config.DATA_DIR, "team_params.json")
        self.params: dict[str, dict] = self._load()
        self.match_count = 0

    def predict_match(self, home_team: str, away_team: str) -> dict:
        home_attack, home_defense = self._get_params(home_team)
        away_attack, away_defense = self._get_params(away_team)

        expected_home = home_attack * away_defense * AVG_HOME_GOALS
        expected_away = away_attack * home_defense * AVG_AWAY_GOALS
        expected_home = max(0.2, expected_home)
        expected_away = max(0.1, expected_away)

        max_prob = 0
        best_home, best_away = 0, 0
        prob_home_win = 0
        prob_away_win = 0
        prob_draw = 0
        outcome_probs = {}

        for hs in range(8):
            for as_ in range(8):
                prob = (pow(expected_home, hs) * exp(-expected_home) / factorial(hs) *
                        pow(expected_away, as_) * exp(-expected_away) / factorial(as_))
                if prob > max_prob:
                    max_prob = prob
                    best_home = hs
                    best_away = as_
                if hs > as_:
                    prob_home_win += prob
                elif as_ > hs:
                    prob_away_win += prob
                else:
                    prob_draw += prob
                outcome_probs[f"{hs}-{as_}"] = round(prob, 4)

        total = prob_home_win + prob_away_win + prob_draw
        prob_home_win /= total
        prob_away_win /= total
        prob_draw /= total

        if best_home == best_away:
            if prob_home_win > prob_away_win:
                best_home += 1
            elif prob_away_win > prob_home_win:
                best_away += 1

        winner = home_team if prob_home_win > prob_away_win else away_team
        if prob_draw > max(prob_home_win, prob_away_win):
            winner = "Draw"

        confidence = max(prob_home_win, prob_away_win, prob_draw)
        confidence = min(round(confidence, 2), 0.92)

        return {
            "winner": winner,
            "home_score": best_home,
            "away_score": best_away,
            "confidence": confidence,
            "expected_home_goals": round(expected_home, 2),
            "expected_away_goals": round(expected_away, 2),
            "home_win_prob": round(prob_home_win, 3),
            "draw_prob": round(prob_draw, 3),
            "away_win_prob": round(prob_away_win, 3),
            "home_attack": home_attack,
            "away_defense": away_defense,
            "away_attack": away_attack,
            "home_defense": home_defense,
        }

    def update_params(self, home: str, away: str, home_score: int, away_score: int):
        home_attack, home_defense = self._get_params(home)
        away_attack, away_defense = self._get_params(away)

        expected_home = home_attack * away_defense * AVG_HOME_GOALS
        expected_away = away_attack * home_defense * AVG_AWAY_GOALS

        learning_rate = 0.05
        home_attack += learning_rate * (home_score - expected_home) / max(expected_home, 0.1)
        away_attack += learning_rate * (away_score - expected_away) / max(expected_away, 0.1)
        home_defense += learning_rate * (away_score - expected_away) * 0.3
        away_defense += learning_rate * (home_score - expected_home) * 0.3

        home_attack = max(0.2, min(2.5, home_attack))
        away_attack = max(0.2, min(2.5, away_attack))
        home_defense = max(0.2, min(2.5, home_defense))
        away_defense = max(0.2, min(2.5, away_defense))

        self.params[home] = {"attack": round(home_attack, 3), "defense": round(home_defense, 2)}
        self.params[away] = {"attack": round(away_attack, 3), "defense": round(away_defense, 2)}
        self.match_count += 1
        self._save()

    def _get_params(self, team: str):
        p = self.params.get(team)
        if p is None:
            return 1.0, 1.0
        return p.get("attack", 1.0), p.get("defense", 1.0)

    @staticmethod
    def _default_params() -> dict:
        return {
            "Brazil": {"attack": 1.8, "defense": 0.6},
            "Argentina": {"attack": 1.7, "defense": 0.7},
            "France": {"attack": 1.6, "defense": 0.7},
            "England": {"attack": 1.5, "defense": 0.7},
            "Spain": {"attack": 1.5, "defense": 0.8},
            "Germany": {"attack": 1.4, "defense": 0.8},
            "Portugal": {"attack": 1.4, "defense": 0.8},
            "Netherlands": {"attack": 1.4, "defense": 0.7},
            "Italy": {"attack": 1.3, "defense": 0.7},
            "Belgium": {"attack": 1.3, "defense": 0.9},
            "Croatia": {"attack": 1.2, "defense": 0.9},
            "Uruguay": {"attack": 1.2, "defense": 0.8},
            "Colombia": {"attack": 1.1, "defense": 0.9},
            "Denmark": {"attack": 1.1, "defense": 0.9},
            "Switzerland": {"attack": 1.0, "defense": 1.0},
            "Japan": {"attack": 1.0, "defense": 1.0},
            "Morocco": {"attack": 0.9, "defense": 0.9},
            "Senegal": {"attack": 0.9, "defense": 1.0},
            "USA": {"attack": 1.0, "defense": 1.1},
            "Mexico": {"attack": 0.9, "defense": 1.0},
            "Poland": {"attack": 1.0, "defense": 1.1},
            "South Korea": {"attack": 0.8, "defense": 1.1},
            "Serbia": {"attack": 1.0, "defense": 1.2},
            "Australia": {"attack": 0.7, "defense": 1.2},
            "Iran": {"attack": 0.7, "defense": 1.1},
            "Nigeria": {"attack": 0.8, "defense": 1.1},
            "Ghana": {"attack": 0.8, "defense": 1.2},
            "Saudi Arabia": {"attack": 0.5, "defense": 1.5},
            "Cameroon": {"attack": 0.7, "defense": 1.3},
            "Tunisia": {"attack": 0.6, "defense": 1.2},
            "Canada": {"attack": 0.8, "defense": 1.2},
            "Ecuador": {"attack": 0.9, "defense": 1.0},
        }

    def _load(self) -> dict:
        defaults = self._default_params()
        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path) as f:
                    saved = json.load(f)
                defaults.update(saved)
                return defaults
            except Exception as e:
                logger.warning(f"Failed to load Poisson params: {e}")
        return defaults

    def _save(self):
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        with open(self.persist_path, "w") as f:
            json.dump(self.params, f, indent=2)
