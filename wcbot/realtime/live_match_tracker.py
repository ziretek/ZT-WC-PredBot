import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class LiveMatchState:
    def __init__(self, match_id: str, home: str, away: str):
        self.match_id = match_id
        self.home_team = home
        self.away_team = away
        self.home_score = 0
        self.away_score = 0
        self.minute = 0
        self.status = "scheduled"  # scheduled, live, halftime, finished
        self.events: list = []
        self.last_checked: float = 0.0


class LiveMatchTracker:
    def __init__(self, data_ingestion=None):
        self._matches: dict[str, LiveMatchState] = {}
        self._data_ingestion = data_ingestion
        self._callbacks = []

    def on_event(self, callback):
        self._callbacks.append(callback)

    def track_match(self, match_id: str, home: str, away: str):
        if match_id not in self._matches:
            self._matches[match_id] = LiveMatchState(match_id, home, away)
            logger.info(f"Now tracking {home} vs {away} ({match_id})")

    def untrack_match(self, match_id: str):
        self._matches.pop(match_id, None)

    async def poll(self) -> list:
        events = []
        now = time.time()

        for match_id, state in list(self._matches.items()):
            if now - state.last_checked < 15:
                continue
            state.last_checked = now

            raw = None
            if self._data_ingestion:
                raw = await self._data_ingestion.fetch_match(match_id)

            if not raw:
                state.minute += 1
                if state.minute > 95 and state.status == "live":
                    state.status = "finished"
                    events.append({
                        "type": "match.finished",
                        "match_id": match_id,
                        "home": state.home_team,
                        "away": state.away_team,
                        "home_score": state.home_score,
                        "away_score": state.away_score,
                    })
                continue

            events.extend(self._detect_events(state, raw))

        for event in events:
            for cb in self._callbacks:
                try:
                    await cb(event)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

        return events

    def _detect_events(self, state: LiveMatchState, raw: dict) -> list:
        events = []
        new_status = raw.get("status", state.status)
        if new_status != state.status:
            old = state.status
            state.status = new_status
            if new_status == "live":
                events.append({"type": "match.started", "match_id": state.match_id,
                               "home": state.home_team, "away": state.away_team})
            elif new_status == "halftime":
                events.append({"type": "match.halftime", "match_id": state.match_id})
            elif new_status == "finished":
                events.append({"type": "match.finished", "match_id": state.match_id,
                               "home": state.home_team, "away": state.away_team,
                               "home_score": state.home_score, "away_score": state.away_score})

        new_home = raw.get("home_score", state.home_score)
        new_away = raw.get("away_score", state.away_score)
        if new_home != state.home_score or new_away != state.away_score:
            events.append({
                "type": "score.changed",
                "match_id": state.match_id,
                "home": state.home_team,
                "away": state.away_team,
                "old_home": state.home_score,
                "old_away": state.away_score,
                "new_home": new_home,
                "new_away": new_away,
            })
            state.home_score = new_home
            state.away_score = new_away

        state.minute = raw.get("minute", state.minute)
        return events

    @property
    def active_count(self) -> int:
        return len([m for m in self._matches.values() if m.status in ("live", "halftime")])

    @property
    def tracked_count(self) -> int:
        return len(self._matches)
