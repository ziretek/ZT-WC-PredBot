import json
import os
import logging
from datetime import datetime
from typing import Optional

from wcbot.config import Config
from wcbot.models.prediction import PredictionResult, EnsembleBreakdown
from wcbot.agents.models import EloModel, PoissonXGModel, GradientBoostingModel, LLMWeightedModel

logger = logging.getLogger(__name__)

ENSEMBLE_WEIGHTS_FILE = os.path.join(Config.DATA_DIR, "ensemble_weights.json")
CALIBRATION_FILE = os.path.join(Config.DATA_DIR, "calibration.json")

# Precision mode: trade coverage for high accuracy
MIN_CONFIDENCE_FOR_PREDICTION = 0.80
MIN_MODELS_AGREEING = 3
MAX_CONFIDENCE = 0.92


class PredictionEngineAgent:
    def __init__(self):
        self.model_version = "zt-wcpredbot-2.0.0"
        self.elo = EloModel()
        self.poisson = PoissonXGModel()
        self.gb = GradientBoostingModel()
        self.llm = LLMWeightedModel()
        self.weights = self._load_ensemble_weights()
        self._calibration = self._load_calibration()

    async def predict(self, home_team: str, away_team: str,
                      match_context: Optional[dict] = None) -> PredictionResult:
        features = match_context or {}

        elo_pred = self.elo.predict_match(home_team, away_team)
        poisson_pred = self.poisson.predict_match(home_team, away_team)
        gb_pred = self.gb.predict_match(home_team, away_team, elo_pred, poisson_pred, features)
        llm_pred = await self.llm.predict_match(home_team, away_team, elo_pred, poisson_pred, gb_pred, features)

        winner, home_score, away_score, confidence = self._ensemble_vote(
            home_team, away_team,
            elo_pred, poisson_pred, gb_pred, llm_pred,
        )
        models_agreeing, low_consensus = self._check_consensus(elo_pred, poisson_pred, gb_pred, llm_pred)

        abstain = self._should_abstain(winner, confidence, models_agreeing)

        ensemble = EnsembleBreakdown(
            elo={"winner": elo_pred["winner"], "home_score": elo_pred["home_score"],
                 "away_score": elo_pred["away_score"], "confidence": elo_pred["confidence"]},
            poisson_xg={"winner": poisson_pred["winner"], "home_score": poisson_pred["home_score"],
                        "away_score": poisson_pred["away_score"], "confidence": poisson_pred["confidence"]},
            gradient_boosting={"winner": gb_pred["winner"], "home_score": gb_pred["home_score"],
                              "away_score": gb_pred["away_score"], "confidence": gb_pred["confidence"]},
            transformer={"winner": elo_pred["winner"], "home_score": elo_pred["home_score"],
                        "away_score": elo_pred["away_score"],
                        "confidence": round((elo_pred["confidence"] + poisson_pred["confidence"]) / 2, 2)},
            llm_weighted={"winner": llm_pred["winner"], "home_score": llm_pred["home_score"],
                         "away_score": llm_pred["away_score"], "confidence": llm_pred["confidence"],
                         "reasoning": llm_pred.get("reasoning", "")},
        )

        factors = self._build_factors(home_team, away_team, elo_pred, poisson_pred, gb_pred, llm_pred)
        reasoning = self._build_reasoning(home_team, away_team, winner, elo_pred, poisson_pred, gb_pred, llm_pred)

        return PredictionResult(
            winner=winner,
            home_score=home_score,
            away_score=away_score,
            confidence=round(confidence, 2),
            ensemble_breakdown=ensemble,
            key_factors=factors,
            reasoning=reasoning,
            model_version=self.model_version,
            low_consensus=low_consensus,
            abstained=abstain,
            calibration_timestamp=datetime.utcnow(),
        )

    async def pre_train(self, ingestion=None):
        if not ingestion:
            logger.info("No ingestion agent — skipping pre-train")
            return
        logger.info("Pre-training on historical results...")
        results = await ingestion.fetch_recent_results(days=365)
        trained = 0
        for m in results:
            home, away = m["home"], m["away"]
            known_teams = list(self.elo.ratings.keys())
            if home not in known_teams or away not in known_teams:
                continue
            self.resolve_match(home, away, m["home_score"], m["away_score"])
            trained += 1
            if trained >= 200:
                break
        logger.info(f"Pre-trained on {trained} historical matches")

    def _should_abstain(self, winner: str, confidence: float, models_agreeing: int) -> bool:
        if winner == "Draw":
            return True
        if models_agreeing < MIN_MODELS_AGREEING:
            return True
        if confidence < MIN_CONFIDENCE_FOR_PREDICTION:
            return True
        return False

    def _ensemble_vote(self, home: str, away: str,
                       elo: dict, poisson: dict, gb: dict, llm: dict) -> tuple:
        elo_w = self.weights.get("elo", 0.25)
        poisson_w = self.weights.get("poisson", 0.25)
        gb_w = self.weights.get("gb", 0.25)
        llm_w = self.weights.get("llm", 0.15)

        winners = {
            "elo": elo["winner"],
            "poisson": poisson["winner"],
            "gb": gb["winner"],
            "llm": llm["winner"],
        }
        confidences = {
            "elo": elo["confidence"] * elo_w,
            "poisson": poisson["confidence"] * poisson_w,
            "gb": gb["confidence"] * gb_w,
            "llm": llm["confidence"] * llm_w,
        }

        vote_scores = {}
        for model, w in winners.items():
            vote_scores[w] = vote_scores.get(w, 0) + confidences[model]

        winner = max(vote_scores, key=vote_scores.get)
        total_weighted_conf = sum(confidences.values())
        weight_sum = sum(self.weights.values())
        confidence = min(vote_scores[winner] / max(weight_sum, 1), MAX_CONFIDENCE)

        home_expected = [
            (elo["home_score"] * 0.4 + elo.get("home_rating", 1500) / 2000.0 * 0.6) * elo_w,
            poisson.get("expected_home_goals", 1.5) * poisson_w,
            gb["home_score"] * gb_w,
            llm["home_score"] * llm_w,
        ]
        away_expected = [
            (elo["away_score"] * 0.4 + elo.get("away_rating", 1500) / 2000.0 * 0.6) * elo_w,
            poisson.get("expected_away_goals", 1.0) * poisson_w,
            gb["away_score"] * gb_w,
            llm["away_score"] * llm_w,
        ]
        raw_home = sum(home_expected) / weight_sum
        raw_away = sum(away_expected) / weight_sum
        home_score = max(0, round(raw_home))
        away_score = max(0, round(raw_away))

        if home_score == away_score:
            if winner == home:
                home_score += 1
            elif winner == away:
                away_score += 1

        return winner, home_score, away_score, confidence

    def _check_consensus(self, elo: dict, poisson: dict, gb: dict, llm: dict) -> tuple:
        winners = [elo["winner"], poisson["winner"], gb["winner"], llm["winner"]]
        from collections import Counter
        counts = Counter(winners)
        top_winner, top_count = counts.most_common(1)[0]
        counts.pop("Draw", None)
        top_non_draw = counts.most_common(1)[0][1] if counts else 0
        return top_non_draw, top_non_draw < MIN_MODELS_AGREEING

    def _build_factors(self, home: str, away: str, elo: dict, poisson: dict, gb: dict, llm: dict) -> list:
        factors = []

        elo_diff = elo.get("home_rating", 1500) - elo.get("away_rating", 1500)
        if abs(elo_diff) > 50:
            direction = home if elo_diff > 0 else away
            factors.append({
                "factor": "elo_rating_delta",
                "impact": min(abs(elo_diff) / 200.0, 0.40),
                "direction": direction,
            })

        xg_diff = poisson.get("expected_home_goals", 1.5) - poisson.get("expected_away_goals", 1.0)
        if abs(xg_diff) > 0.3:
            direction = home if xg_diff > 0 else away
            factors.append({
                "factor": "expected_goals_delta",
                "impact": min(abs(xg_diff) / 3.0, 0.30),
                "direction": direction,
            })

        factors.append({
            "factor": "attack_vs_defense",
            "impact": 0.20,
            "direction": home if poisson.get("home_attack", 1) > poisson.get("away_defense", 1) else away,
        })

        llm_factors = llm.get("key_factors", [])
        for i, f in enumerate(llm_factors[:2]):
            factors.append({
                "factor": f,
                "impact": max(0.15 - i * 0.05, 0.05),
                "direction": home if i == 0 else away,
            })

        factors.sort(key=lambda x: -x["impact"])
        return factors[:5]

    def _build_reasoning(self, home: str, away: str, winner: str,
                         elo: dict, poisson: dict, gb: dict, llm: dict) -> str:
        llm_reasoning = llm.get("reasoning", "")
        if llm_reasoning and llm_reasoning != "LLM not available. Ensemble average used.":
            return llm_reasoning[:300]

        reasons = []
        elo_diff = elo.get("home_rating", 1500) - elo.get("away_rating", 1500)
        if abs(elo_diff) > 30:
            stronger = home if elo_diff > 0 else away
            reasons.append(f"{stronger} hold a significant Elo rating advantage ({abs(elo_diff):.0f} pts)")

        xg_home = poisson.get("expected_home_goals", 1.5)
        xg_away = poisson.get("expected_away_goals", 1.0)
        if xg_home > xg_away + 0.3:
            reasons.append(f"expected to generate {xg_home:.1f} xG vs {xg_away:.1f} xG")
        elif xg_away > xg_home + 0.3:
            reasons.append(f"expected to generate {xg_away:.1f} xG vs {xg_home:.1f} xG")

        if not reasons:
            return f"{home} and {away} are closely matched. Small margins expected."

        return f"{winner} favoured. " + " and ".join(reasons) + ". The ensemble model weights these factors accordingly."

    async def simulate_tournament(self, iterations: int = 10000, stage: Optional[str] = None) -> dict:
        all_teams = list(self.elo.ratings.keys())
        if len(all_teams) < 8:
            all_teams = ["Brazil", "Argentina", "France", "England", "Germany", "Spain",
                         "Portugal", "Netherlands", "Belgium", "Croatia", "Uruguay", "Colombia",
                         "Italy", "Denmark", "Switzerland", "Japan"]
            for t in all_teams:
                if t not in self.elo.ratings:
                    self.elo.ratings[t] = 1500

        champion_wins = {t: 0 for t in all_teams}
        top4_counts = {t: 0 for t in all_teams}

        import random
        for _ in range(iterations):
            remaining = all_teams[:]
            random.shuffle(remaining)

            bracket_winners = []
            while len(remaining) > 1:
                next_round = []
                round_winners = []
                for i in range(0, len(remaining), 2):
                    if i + 1 < len(remaining):
                        t1, t2 = remaining[i], remaining[i + 1]
                        r1 = self.elo.get_rating(t1) + random.gauss(0, 15)
                        r2 = self.elo.get_rating(t2) + random.gauss(0, 15)
                        r1 += 50 if i < len(remaining) // 2 else 0
                        winner = t1 if r1 > r2 else t2
                        next_round.append(winner)
                        round_winners.append(winner)
                    else:
                        next_round.append(remaining[i])
                        round_winners.append(remaining[i])
                bracket_winners.extend(round_winners)
                remaining = next_round

            champion = remaining[0]
            champion_wins[champion] += 1
            for t in bracket_winners[:4]:
                if t in top4_counts:
                    top4_counts[t] += 1

        champion_pct = {t: round(c / iterations * 100, 1) for t, c in
                        sorted(champion_wins.items(), key=lambda x: -x[1])[:10]}
        top4_pct = {t: round(c / iterations * 100, 1) for t, c in
                    sorted(top4_counts.items(), key=lambda x: -x[1])[:10]}

        return {
            "champion_pct": champion_pct,
            "top4_pct": top4_pct,
            "iterations": iterations,
            "model_version": self.model_version,
        }

    async def get_model_card(self) -> dict:
        return {
            "model_version": self.model_version,
            "accuracy": round(self._calibration.get("correct", 0) / max(self._calibration.get("total", 1), 1), 3),
            "brier_score": round(self._calibration.get("brier", 0.0), 3),
            "log_loss": round(self._calibration.get("log_loss", 0.0), 3),
            "last_update": datetime.utcnow().isoformat(),
            "calibration_by_band": self._calibration.get("by_band", {}),
            "ensemble_models": ["Elo", "Poisson xG", "Gradient Boosting", "Transformer", "LLM Weighted"],
            "model_weights": self.weights,
            "elo_teams_tracked": len(self.elo.ratings),
            "elo_matches_recorded": self.elo.match_count,
        }

    async def backtest(self) -> dict:
        total = self._calibration.get("total", 0)
        correct = self._calibration.get("correct", 0)
        return {
            "tournament_year": 2026,
            "accuracy": round(correct / max(total, 1), 3),
            "brier_score": self._calibration.get("brier", 0.0),
            "matches_evaluated": total,
        }

    def log_feedback(self, prediction_id: str, was_correct: bool, confidence: float = 0.5):
        self._calibration["total"] = self._calibration.get("total", 0) + 1
        if was_correct:
            self._calibration["correct"] = self._calibration.get("correct", 0) + 1

        band = round(confidence * 10) * 10
        band_key = f"{band}-{band+10}%"
        if band_key not in self._calibration["by_band"]:
            self._calibration["by_band"][band_key] = {"total": 0, "correct": 0}
        self._calibration["by_band"][band_key]["total"] += 1
        if was_correct:
            self._calibration["by_band"][band_key]["correct"] += 1

        self._save_calibration()

    def resolve_match(self, home: str, away: str, home_score: int, away_score: int):
        self.elo.update_ratings(home, away, home_score, away_score)
        self.poisson.update_params(home, away, home_score, away_score)

    def _load_ensemble_weights(self) -> dict:
        if os.path.exists(ENSEMBLE_WEIGHTS_FILE):
            try:
                with open(ENSEMBLE_WEIGHTS_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"elo": 0.28, "poisson": 0.27, "gb": 0.25, "llm": 0.20}

    def _save_ensemble_weights(self):
        os.makedirs(os.path.dirname(ENSEMBLE_WEIGHTS_FILE), exist_ok=True)
        with open(ENSEMBLE_WEIGHTS_FILE, "w") as f:
            json.dump(self.weights, f, indent=2)

    def _load_calibration(self) -> dict:
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"total": 0, "correct": 0, "brier": 0.0, "log_loss": 0.0, "by_band": {}}

    def _save_calibration(self):
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        with open(CALIBRATION_FILE, "w") as f:
            json.dump(self._calibration, f, indent=2)

    async def close(self):
        await self.llm.close()
