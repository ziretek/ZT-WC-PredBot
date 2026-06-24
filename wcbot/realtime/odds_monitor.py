import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class OddsState:
    def __init__(self, match_id: str):
        self.match_id = match_id
        self.home_odds: float = 0.0
        self.draw_odds: float = 0.0
        self.away_odds: float = 0.0
        self.last_checked: float = 0.0


class OddsMonitor:
    def __init__(self, data_ingestion=None):
        self._odds: dict[str, OddsState] = {}
        self._data_ingestion = data_ingestion
        self._callbacks = []
        self.SWING_THRESHOLD = 0.15

    def on_swing(self, callback):
        self._callbacks.append(callback)

    def track_match(self, match_id: str):
        if match_id not in self._odds:
            self._odds[match_id] = OddsState(match_id)

    async def poll(self) -> list:
        swings = []
        now = time.time()

        for match_id, state in list(self._odds.items()):
            if now - state.last_checked < 60:
                continue
            state.last_checked = now

            odds_data = None
            if self._data_ingestion:
                odds_data = await self._data_ingestion.fetch_odds(match_id)

            if not odds_data:
                continue

            new_home = odds_data.get("home_odds", state.home_odds)
            new_away = odds_data.get("away_odds", state.away_odds)
            new_draw = odds_data.get("draw_odds", state.draw_odds)

            if state.home_odds > 0:
                home_swing = abs(new_home - state.home_odds) / state.home_odds
                away_swing = abs(new_away - state.away_odds) / state.away_odds
                draw_swing = abs(new_draw - state.draw_odds) / state.draw_odds

                max_swing = max(home_swing, away_swing, draw_swing)
                if max_swing >= self.SWING_THRESHOLD:
                    swing_event = {
                        "type": "odds.swing",
                        "match_id": match_id,
                        "old": {"home": state.home_odds, "draw": state.draw_odds, "away": state.away_odds},
                        "new": {"home": new_home, "draw": new_draw, "away": new_away},
                        "swing_pct": round(max_swing * 100, 1),
                    }
                    swings.append(swing_event)
                    logger.info(f"Odds swing {max_swing:.1%} on {match_id}")

            state.home_odds = new_home
            state.draw_odds = new_draw
            state.away_odds = new_away

        for swing in swings:
            for cb in self._callbacks:
                try:
                    await cb(swing)
                except Exception as e:
                    logger.error(f"Odds callback error: {e}")

        return swings
