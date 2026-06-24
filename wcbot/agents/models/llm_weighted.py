import logging
import json
from typing import Optional

from wcbot.config import Config

logger = logging.getLogger(__name__)


class LLMWeightedModel:
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or Config.OPENAI_API_KEY
        self.api_url = api_url or Config.OPENAI_API_URL
        self.model = model or Config.LLM_MODEL
        self.http_client = None

    async def predict_match(self, home_team: str, away_team: str,
                            elo_pred: dict, poisson_pred: dict, gb_pred: dict,
                            features: dict) -> dict:
        if not self.api_key:
            return self._fallback(home_team, away_team, elo_pred, poisson_pred, gb_pred)

        prompt = self._build_prompt(home_team, away_team, elo_pred, poisson_pred, gb_pred, features)
        llm_response = await self._call_llm(prompt)

        if llm_response:
            return self._parse_response(llm_response, home_team, away_team, elo_pred, poisson_pred, gb_pred)
        return self._fallback(home_team, away_team, elo_pred, poisson_pred, gb_pred)

    def _build_prompt(self, home: str, away: str,
                      elo: dict, poisson: dict, gb: dict, features: dict) -> str:
        return f"""You are a world-class football prediction analyst for the 2026 World Cup.

Match: {home} vs {away}

Elo Model:
- {home} rating: {elo.get('home_rating', '?')}, {away} rating: {elo.get('away_rating', '?')}
- Home win: {elo.get('home_win_prob', 0):.0%}, Draw: {elo.get('draw_prob', 0):.0%}, Away win: {elo.get('away_win_prob', 0):.0%}

Poisson xG Model:
- Expected goals: {home} {poisson.get('expected_home_goals', 0):.2f} - {poisson.get('expected_away_goals', 0):.2f} {away}
- {home} attack: {poisson.get('home_attack', 1.0):.2f}, defense: {poisson.get('home_defense', 0):.2f}
- {away} attack: {poisson.get('away_attack', 1.0):.2f}, defense: {poisson.get('away_defense', 0):.2f}

Gradient Boosting:
- Home win prob: {gb.get('home_win_prob', 0):.0%}

Context: World Cup 2026 match.

Respond in JSON format with exactly these fields:
{{"winner": "<team or Draw>", "home_score": <int>, "away_score": <int>, "confidence": <0.0-1.0>, "reasoning": "<2 sentence analysis>", "key_factors": ["<factor1>", "<factor2>", "<factor3>"]}}"""

    async def _call_llm(self, prompt: str) -> Optional[dict]:
        try:
            if not self.http_client:
                import httpx
                self.http_client = httpx.AsyncClient(timeout=20.0)

            resp = await self.http_client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
            return None

    def _parse_response(self, llm_resp: dict, home: str, away: str,
                        elo: dict, poisson: dict, gb: dict) -> dict:
        confidence = min(float(llm_resp.get("confidence", 0.5)), 0.88)
        return {
            "winner": llm_resp.get("winner", home),
            "home_score": int(llm_resp.get("home_score", 1)),
            "away_score": int(llm_resp.get("away_score", 1)),
            "confidence": round(confidence, 2),
            "home_win_prob": round(confidence * 0.65, 3),
            "draw_prob": round(0.20, 3),
            "away_win_prob": round((1.0 - confidence) * 0.85, 3),
            "reasoning": llm_resp.get("reasoning", ""),
            "key_factors": llm_resp.get("key_factors", []),
        }

    async def answer_question(self, question: str) -> Optional[str]:
        if not self.api_key:
            return None
        prompt = f"""You are a knowledgeable 2026 World Cup assistant. Answer concisely.

Question: {question}

Rules:
- Answer in 2-3 sentences.
- Only talk about the 2026 World Cup.
- If you don't know the answer, say so — don't make things up.
- Use plain text, not JSON."""

        try:
            if not self.http_client:
                import httpx
                self.http_client = httpx.AsyncClient(timeout=20.0)

            resp = await self.http_client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "max_tokens": 250,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"LLM Q&A failed: {e}")
            return None

    def _fallback(self, home: str, away: str,
                  elo: dict, poisson: dict, gb: dict) -> dict:
        confidences = [
            elo.get("confidence", 0.5),
            poisson.get("confidence", 0.5),
            gb.get("confidence", 0.5),
        ]
        avg_confidence = round(sum(confidences) / len(confidences), 2)

        scores = [
            (elo.get("home_score", 1), elo.get("away_score", 1)),
            (poisson.get("home_score", 1), poisson.get("away_score", 1)),
            (gb.get("home_score", 1), gb.get("away_score", 1)),
        ]
        avg_home = round(sum(s[0] for s in scores) / len(scores))
        avg_away = round(sum(s[1] for s in scores) / len(scores))

        winners = [elo.get("winner"), poisson.get("winner"), gb.get("winner")]
        from collections import Counter
        winner_counts = Counter(winners)
        winner = winner_counts.most_common(1)[0][0]

        if avg_home == avg_away:
            if winner == home:
                avg_home += 1
            elif winner == away:
                avg_away += 1

        return {
            "winner": winner,
            "home_score": avg_home,
            "away_score": avg_away,
            "confidence": avg_confidence,
            "reasoning": "LLM not available. Ensemble average used.",
            "key_factors": ["ensemble_average", "no_llm"],
        }

    async def close(self):
        if self.http_client:
            await self.http_client.aclose()
