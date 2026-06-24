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

    async def fetch_recent_results(self, days: int = 365) -> list:
        if not Config.SPORTS_API_KEY:
            return []
        cache_key = f"results:{days}"
        cached = self._get_cached(cache_key, ttl=3600)
        if cached:
            return cached
        try:
            since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
            resp = await self._http_client.get(
                "https://api.sportmonks.com/v3/football/fixtures",
                params={
                    "api_token": Config.SPORTS_API_KEY,
                    "filters": f"starts_after:{since}",
                    "include": "localTeam,visitorTeam",
                    "per_page": 100,
                },
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            results = []
            for m in data:
                status = m.get("status", "")
                if status not in ("finished", "ft"):
                    continue
                home_team = m.get("localTeam", {}).get("data", {}).get("name", "")
                away_team = m.get("visitorTeam", {}).get("data", {}).get("name", "")
                scores = m.get("scores", {})
                home_score = scores.get("localteam_score", 0)
                away_score = scores.get("visitorteam_score", 0)
                if home_team and away_team:
                    results.append({
                        "home": home_team, "away": away_team,
                        "home_score": home_score, "away_score": away_score,
                    })
            self._set_cache(cache_key, results, ttl=3600)
            logger.info(f"Fetched {len(results)} recent results")
            return results
        except Exception as e:
            logger.warning(f"Failed to fetch results: {e}")
            return []

    async def fetch_injuries(self, team: str) -> list:
        if not Config.SPORTS_API_KEY:
            return []
        cache_key = f"injuries:{team}"
        cached = self._get_cached(cache_key, ttl=600)
        if cached:
            return cached
        try:
            resp = await self._http_client.get(
                "https://api.sportmonks.com/v3/football/injuries",
                params={
                    "api_token": Config.SPORTS_API_KEY,
                    "filters": f"team_name:{team}",
                    "per_page": 20,
                },
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            injuries = []
            for inj in data:
                injuries.append({
                    "player": inj.get("player", {}).get("data", {}).get("name", "Unknown"),
                    "type": inj.get("type", "injury"),
                    "return_date": inj.get("return_date", "unknown"),
                })
            self._set_cache(cache_key, injuries, ttl=600)
            return injuries
        except Exception:
            return []

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
            normalized = self._normalize_standing_entry(entry)
            if not normalized:
                continue
            groups.setdefault(normalized["group"], []).append(normalized)

        if not groups:
            logger.info("Standings data is available but not in World Cup group-table shape")
            return []

        advancing = []
        for g in sorted(groups.keys()):
            sorted_teams = sorted(groups[g], key=lambda t: (-t["points"], -t["goal_diff"]))
            advancing.extend(sorted_teams[:2])

        return sorted(advancing, key=lambda t: t["group"])

    def _normalize_standing_entry(self, entry: dict) -> Optional[dict]:
        group = entry.get("group") or entry.get("group_name")
        if isinstance(group, dict):
            group = group.get("name") or group.get("data", {}).get("name")

        participant = entry.get("participant") or entry.get("team") or entry.get("participant_data")
        name = entry.get("name") or entry.get("team_name")
        if isinstance(participant, dict):
            name = name or participant.get("name") or participant.get("data", {}).get("name")

        points = entry.get("points")
        goal_diff = entry.get("goal_diff", entry.get("goal_difference"))
        result = entry.get("result")
        if isinstance(result, dict):
            points = points if points is not None else result.get("points")
            goal_diff = goal_diff if goal_diff is not None else result.get("goal_difference", result.get("goal_diff"))

        if not group or not name:
            return None

        try:
            points = int(points or 0)
        except (TypeError, ValueError):
            points = 0
        try:
            goal_diff = int(goal_diff or 0)
        except (TypeError, ValueError):
            goal_diff = 0

        return {
            "group": str(group),
            "name": str(name),
            "points": points,
            "goal_diff": goal_diff,
        }

    def _get_cached(self, key: str, ttl: int = 30):
        entry = self._cache.get(key)
        if entry and (datetime.utcnow() - entry["timestamp"]).seconds < ttl:
            return entry["data"]
        return None

    def _set_cache(self, key: str, data, ttl: int = 30):
        self._cache[key] = {"data": data, "timestamp": datetime.utcnow()}

    async def close(self):
        await self._http_client.aclose()
