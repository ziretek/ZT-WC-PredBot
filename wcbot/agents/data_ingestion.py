import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from wcbot.config import Config
from wcbot.utils.teams import normalize_team_name

logger = logging.getLogger(__name__)

WORLD_CUP_SPORT_KEY = "soccer_fifa_world_cup"
WORLD_CUP_WINNER_KEY = "soccer_fifa_world_cup_winner"
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"


class DataIngestionAgent:
    def __init__(self):
        self._cache = {}
        self._http_client = httpx.AsyncClient(timeout=15.0)

    async def fetch_match(self, match_id: str) -> Optional[dict]:
        cache_key = f"match:{match_id}"
        cached = self._get_cached(cache_key, ttl=30)
        if cached:
            return cached

        if Config.ODDS_API_KEY:
            scores = await self.fetch_world_cup_scores()
            match = next((item for item in scores if item.get("id") == match_id), None)
            if match:
                status = match.get("status", "scheduled")
                return {**match, "status": "finished" if status == "completed" else status}

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

    async def fetch_odds(self, match_id: str) -> dict:
        cache_key = f"odds:{match_id}"
        cached = self._get_cached(cache_key, ttl=600)
        if cached:
            return cached

        if not Config.ODDS_API_KEY:
            return {}
        events = await self.fetch_world_cup_odds()
        data = next((event for event in events if event.get("id") == match_id), {})
        self._set_cache(cache_key, data, ttl=600)
        return data

    async def fetch_world_cup_events(self) -> list:
        cache_key = "world_cup:events"
        cached = self._get_cached(cache_key, ttl=300)
        if cached is not None:
            return cached
        if not Config.ODDS_API_KEY:
            return []

        try:
            resp = await self._http_client.get(
                f"{ODDS_API_BASE}/{WORLD_CUP_SPORT_KEY}/events",
                params={"apiKey": Config.ODDS_API_KEY},
            )
            resp.raise_for_status()
            events = [self._normalize_event(event) for event in resp.json()]
            events = [event for event in events if event]
            events.sort(key=lambda event: event["commence_time"])
            self._set_cache(cache_key, events, ttl=300)
            return events
        except Exception as e:
            logger.warning("Failed to fetch World Cup events: %s", e)
            return []

    async def fetch_world_cup_odds(self) -> list:
        cache_key = "world_cup:odds"
        cached = self._get_cached(cache_key, ttl=600)
        if cached is not None:
            return cached
        if not Config.ODDS_API_KEY:
            return []

        try:
            resp = await self._http_client.get(
                f"{ODDS_API_BASE}/{WORLD_CUP_SPORT_KEY}/odds",
                params={
                    "apiKey": Config.ODDS_API_KEY,
                    "regions": "eu",
                    "markets": "h2h",
                    "oddsFormat": "decimal",
                },
            )
            resp.raise_for_status()
            events = [self._normalize_odds_event(event) for event in resp.json()]
            events = [event for event in events if event]
            events.sort(key=lambda event: event["commence_time"])
            self._set_cache(cache_key, events, ttl=600)
            return events
        except Exception as e:
            logger.warning("Failed to fetch World Cup odds: %s", e)
            return []

    async def fetch_world_cup_scores(self, days: int = 3) -> list:
        days = max(1, min(days, 3))
        cache_key = f"world_cup:scores:{days}"
        cached = self._get_cached(cache_key, ttl=300)
        if cached is not None:
            return cached
        if not Config.ODDS_API_KEY:
            return []

        try:
            resp = await self._http_client.get(
                f"{ODDS_API_BASE}/{WORLD_CUP_SPORT_KEY}/scores",
                params={"apiKey": Config.ODDS_API_KEY, "daysFrom": days},
            )
            resp.raise_for_status()
            matches = [self._normalize_score_event(event) for event in resp.json()]
            matches = [match for match in matches if match]
            matches.sort(key=lambda match: match["commence_time"], reverse=True)
            self._set_cache(cache_key, matches, ttl=300)
            return matches
        except Exception as e:
            logger.warning("Failed to fetch World Cup scores: %s", e)
            return []

    async def find_world_cup_match(self, home: str, away: str) -> Optional[dict]:
        requested = {home, away}
        scores = await self.fetch_world_cup_scores()
        for event in await self.fetch_world_cup_odds():
            if {event["home_team"], event["away_team"]} == requested:
                score_state = next((match for match in scores if match.get("id") == event.get("id")), None)
                return {**event, **score_state} if score_state else event
        for match in scores:
            if {match["home_team"], match["away_team"]} == requested:
                return match
        return None

    async def fetch_world_cup_winner_odds(self) -> list:
        cache_key = "world_cup:winner_odds"
        cached = self._get_cached(cache_key, ttl=1800)
        if cached is not None:
            return cached
        if not Config.ODDS_API_KEY:
            return []

        try:
            resp = await self._http_client.get(
                f"{ODDS_API_BASE}/{WORLD_CUP_WINNER_KEY}/odds",
                params={
                    "apiKey": Config.ODDS_API_KEY,
                    "regions": "eu",
                    "markets": "outrights",
                    "oddsFormat": "decimal",
                },
            )
            resp.raise_for_status()
            events = resp.json()
            if not events:
                return []

            probabilities = defaultdict(list)
            prices = defaultdict(list)
            for bookmaker in events[0].get("bookmakers", []):
                market = next(
                    (market for market in bookmaker.get("markets", []) if market.get("key") == "outrights"),
                    None,
                )
                if not market:
                    continue
                valid = [outcome for outcome in market.get("outcomes", []) if float(outcome.get("price", 0)) > 1]
                raw_total = sum(1.0 / float(outcome["price"]) for outcome in valid)
                if not raw_total:
                    continue
                for outcome in valid:
                    team = normalize_team_name(outcome.get("name", "")) or outcome.get("name", "")
                    price = float(outcome["price"])
                    probabilities[team].append((1.0 / price) / raw_total)
                    prices[team].append(price)

            result = [
                {
                    "team": team,
                    "probability": sum(values) / len(values),
                    "decimal_odds": sum(prices[team]) / len(prices[team]),
                }
                for team, values in probabilities.items()
            ]
            result.sort(key=lambda item: item["probability"], reverse=True)
            self._set_cache(cache_key, result, ttl=1800)
            return result
        except Exception as e:
            logger.warning("Failed to fetch World Cup winner odds: %s", e)
            return []

    def _normalize_event(self, event: dict) -> Optional[dict]:
        home = normalize_team_name(event.get("home_team", ""))
        away = normalize_team_name(event.get("away_team", ""))
        if not home or not away:
            return None
        status = "scheduled"
        commence_time = event.get("commence_time", "")
        if commence_time:
            try:
                kickoff = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
                if kickoff <= datetime.now(timezone.utc):
                    status = "live"
            except ValueError:
                pass
        return {
            "id": event.get("id", ""),
            "home_team": home,
            "away_team": away,
            "commence_time": commence_time,
            "status": status,
            "source": "The Odds API",
        }

    def _normalize_odds_event(self, event: dict) -> Optional[dict]:
        normalized = self._normalize_event(event)
        if not normalized:
            return None

        home_prices = []
        draw_prices = []
        away_prices = []
        probability_rows = []
        for bookmaker in event.get("bookmakers", []):
            market = next(
                (market for market in bookmaker.get("markets", []) if market.get("key") == "h2h"),
                None,
            )
            if not market:
                continue
            prices = {outcome.get("name"): float(outcome.get("price", 0)) for outcome in market.get("outcomes", [])}
            raw_home = prices.get(event.get("home_team"), 0)
            raw_draw = prices.get("Draw", 0)
            raw_away = prices.get(event.get("away_team"), 0)
            if min(raw_home, raw_draw, raw_away) <= 1:
                continue
            implied = [1.0 / raw_home, 1.0 / raw_draw, 1.0 / raw_away]
            total = sum(implied)
            probability_rows.append([value / total for value in implied])
            home_prices.append(raw_home)
            draw_prices.append(raw_draw)
            away_prices.append(raw_away)

        if probability_rows:
            normalized.update({
                "market_home_prob": sum(row[0] for row in probability_rows) / len(probability_rows),
                "market_draw_prob": sum(row[1] for row in probability_rows) / len(probability_rows),
                "market_away_prob": sum(row[2] for row in probability_rows) / len(probability_rows),
                "home_odds": sum(home_prices) / len(home_prices),
                "draw_odds": sum(draw_prices) / len(draw_prices),
                "away_odds": sum(away_prices) / len(away_prices),
                "bookmaker_count": len(probability_rows),
            })
        return normalized

    def _normalize_score_event(self, event: dict) -> Optional[dict]:
        normalized = self._normalize_event(event)
        if not normalized:
            return None
        scores = {score.get("name"): score.get("score") for score in event.get("scores") or []}
        status = "completed" if event.get("completed") else "scheduled"
        if not event.get("completed") and event.get("scores"):
            status = "live"
        elif not event.get("completed") and normalized.get("commence_time"):
            try:
                kickoff = datetime.fromisoformat(normalized["commence_time"].replace("Z", "+00:00"))
                if kickoff <= datetime.now(timezone.utc):
                    status = "live"
            except ValueError:
                pass
        normalized.update({
            "status": status,
            "home_score": self._to_int(scores.get(event.get("home_team"))),
            "away_score": self._to_int(scores.get(event.get("away_team"))),
            "last_update": event.get("last_update"),
        })
        return normalized

    @staticmethod
    def _to_int(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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

    async def fetch_lineups(self, match_id: str) -> dict:
        # The configured tournament feeds do not currently include lineups.
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
