import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from wcbot.config import Config

logger = logging.getLogger(__name__)


class DataIngestionAgent:
    def __init__(self):
        self._cache = {}
        self._http_client = httpx.AsyncClient(timeout=15.0)

    async def fetch_features(self, home: str, away: str) -> dict:
        features = {
            "rest_days_diff": 0,
            "travel_distance_km": 0,
            "home_advantage": 1.0,
            "knockout_pressure": 0.5,
            "temperature": 22,
            "referee_card_rate": 3.5,
        }

        h2h = await self.fetch_head2head(home, away)
        features["h2h_home_wins"] = h2h.get("team1_wins", 0)
        features["h2h_away_wins"] = h2h.get("team2_wins", 0)
        features["h2h_draws"] = h2h.get("draws", 0)

        return features

    async def fetch_match(self, match_id: str) -> Optional[dict]:
        cache_key = f"match:{match_id}"
        cached = self._get_cached(cache_key, ttl=30)
        if cached:
            return cached

        if not Config.SPORTS_API_KEY:
            return None

        try:
            resp = await self._http_client.get(
                f"https://api.sportmonks.com/v3/football/fixtures/{match_id}",
                params={
                    "api_token": Config.SPORTS_API_KEY,
                    "include": "localTeam,visitorTeam,venue,weather",
                },
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            self._set_cache(cache_key, data, ttl=30)
            return data
        except Exception as e:
            logger.warning(f"Failed to fetch match {match_id}: {e}")
            return None

    async def fetch_standings(self, group: Optional[str] = None) -> list:
        cache_key = f"standings:{group or 'all'}"
        cached = self._get_cached(cache_key, ttl=60)
        if cached:
            return cached

        if not Config.SPORTS_API_KEY:
            return []

        try:
            params = {"api_token": Config.SPORTS_API_KEY}
            resp = await self._http_client.get(
                "https://api.sportmonks.com/v3/football/standings",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            self._set_cache(cache_key, data, ttl=60)
            return data
        except Exception as e:
            logger.warning(f"Failed to fetch standings: {e}")
            return []

    async def fetch_head2head(self, team1: str, team2: str, n: int = 10) -> dict:
        cache_key = f"h2h:{team1}:{team2}:{n}"
        cached = self._get_cached(cache_key, ttl=3600)
        if cached:
            return cached

        h2h = {
            "team1": team1,
            "team2": team2,
            "team1_wins": 3,
            "team2_wins": 2,
            "draws": 5,
            "team1_avg_xg": 1.4,
            "team2_avg_xg": 1.2,
            "recent_meetings": [],
        }
        self._set_cache(cache_key, h2h, ttl=3600)
        return h2h

    async def fetch_odds(self, match_id: str) -> dict:
        cache_key = f"odds:{match_id}"
        cached = self._get_cached(cache_key, ttl=60)
        if cached:
            return cached

        if not Config.ODDS_API_KEY:
            return {}

        try:
            resp = await self._http_client.get(
                "https://api.the-odds-api.com/v4/sports/soccer_world_cup/odds",
                params={
                    "apiKey": Config.ODDS_API_KEY,
                    "regions": "eu",
                    "markets": "h2h,spreads,totals",
                    "eventIds": match_id,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._set_cache(cache_key, data, ttl=60)
            return data
        except Exception as e:
            logger.warning(f"Failed to fetch odds: {e}")
            return {}

    async def health_check(self) -> bool:
        if Config.SPORTS_API_KEY:
            try:
                resp = await self._http_client.get(
                    "https://api.sportmonks.com/v3/football/fixtures",
                    params={"api_token": Config.SPORTS_API_KEY, "per_page": 1},
                )
                return resp.is_success
            except Exception:
                return False
        return True

    async def fetch_round_of_32(self) -> list:
        standings = await self.fetch_standings()
        if not standings:
            return []

        groups = {}
        for entry in standings:
            g = entry["group"]
            groups.setdefault(g, []).append(entry)

        advancing = []
        for g in sorted(groups.keys()):
            sorted_teams = sorted(groups[g], key=lambda t: (-t["points"], -t["goal_diff"]))
            advancing.extend(sorted_teams[:2])

        return sorted(advancing, key=lambda t: t["group"])

    def _get_cached(self, key: str, ttl: int = 30):
        entry = self._cache.get(key)
        if entry and (datetime.utcnow() - entry["timestamp"]).seconds < ttl:
            return entry["data"]
        return None

    def _set_cache(self, key: str, data, ttl: int = 30):
        self._cache[key] = {"data": data, "timestamp": datetime.utcnow()}

    async def close(self):
        await self._http_client.aclose()
