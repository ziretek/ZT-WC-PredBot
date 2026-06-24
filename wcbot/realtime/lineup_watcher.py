import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class LineupState:
    def __init__(self, match_id: str):
        self.match_id = match_id
        self.home_lineup_confirmed: bool = False
        self.away_lineup_confirmed: bool = False
        self.home_xi: list = []
        self.away_xi: list = []
        self.last_checked: float = 0.0


class LineupWatcher:
    def __init__(self, data_ingestion=None):
        self._lineups: dict[str, LineupState] = {}
        self._data_ingestion = data_ingestion
        self._callbacks = []

    def on_lineup_confirmed(self, callback):
        self._callbacks.append(callback)

    def track_match(self, match_id: str):
        if match_id not in self._lineups:
            self._lineups[match_id] = LineupState(match_id)

    async def poll(self) -> list:
        confirmations = []
        now = time.time()

        for match_id, state in list(self._lineups.items()):
            if state.home_lineup_confirmed and state.away_lineup_confirmed:
                continue
            if now - state.last_checked < 120:
                continue
            state.last_checked = now

            lineups_data = None
            if self._data_ingestion:
                lineups_data = await self._data_ingestion.fetch_lineups(match_id)

            if not lineups_data:
                continue

            home_players = lineups_data.get("home", {}).get("players", [])
            away_players = lineups_data.get("away", {}).get("players", [])

            if home_players and not state.home_lineup_confirmed:
                state.home_lineup_confirmed = True
                state.home_xi = home_players
                confirmations.append({
                    "type": "lineup.confirmed",
                    "match_id": match_id,
                    "team": "home",
                    "formation": lineups_data.get("home", {}).get("formation", "?"),
                    "strength": lineups_data.get("home", {}).get("strength", 0),
                })

            if away_players and not state.away_lineup_confirmed:
                state.away_lineup_confirmed = True
                state.away_xi = away_players
                confirmations.append({
                    "type": "lineup.confirmed",
                    "match_id": match_id,
                    "team": "away",
                    "formation": lineups_data.get("away", {}).get("formation", "?"),
                    "strength": lineups_data.get("away", {}).get("strength", 0),
                })

        for event in confirmations:
            for cb in self._callbacks:
                try:
                    await cb(event)
                except Exception as e:
                    logger.error(f"Lineup callback error: {e}")

        return confirmations
