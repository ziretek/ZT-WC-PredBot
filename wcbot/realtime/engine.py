import asyncio
import logging
from datetime import datetime

from wcbot.realtime.live_match_tracker import LiveMatchTracker
from wcbot.realtime.odds_monitor import OddsMonitor
from wcbot.realtime.lineup_watcher import LineupWatcher
from wcbot.realtime.push_notifier import PushNotifier
from wcbot.utils.live_tournament import fixture_context

logger = logging.getLogger(__name__)


class RealtimeEngine:
    def __init__(self, app=None, data_ingestion=None, state_manager=None, prediction_engine=None):
        self._app = app
        self._running = False
        self._task = None

        self.match_tracker = LiveMatchTracker(data_ingestion)
        self.odds_monitor = OddsMonitor(data_ingestion)
        self.lineup_watcher = LineupWatcher(data_ingestion)
        self.push_notifier = PushNotifier(app, state_manager)

        self._data_ingestion = data_ingestion
        self._state_manager = state_manager
        self._prediction_engine = prediction_engine

        self.match_tracker.on_event(self._on_match_event)
        self.odds_monitor.on_swing(self._on_odds_swing)
        self.lineup_watcher.on_lineup_confirmed(self._on_lineup_event)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Realtime engine started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Realtime engine stopped")

    def track_match(self, match_id: str, home: str, away: str):
        self.match_tracker.track_match(match_id, home, away)
        self.odds_monitor.track_match(match_id)
        logger.info(f"Realtime tracking enabled for {home} vs {away} ({match_id})")

    async def _run_loop(self):
        while self._running:
            try:
                await self.match_tracker.poll()
                await self.odds_monitor.poll()
                await self.lineup_watcher.poll()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Realtime poll error: {e}")
            await asyncio.sleep(10)

    async def _on_match_event(self, event: dict):
        event_type = event.get("type", "")

        if event_type == "score.changed":
            logger.info(f"Score: {event['home']} {event['new_home']}-{event['new_away']} {event['away']}")
            if self._prediction_engine:
                fixture = None
                if self._data_ingestion:
                    fixture = await self._data_ingestion.find_world_cup_match(event["home"], event["away"])
                context = fixture_context(fixture) if fixture else {}
                context.update({
                    "live_home_score": event["new_home"],
                    "live_away_score": event["new_away"],
                })
                new_pred = await self._prediction_engine.predict(event["home"], event["away"], context)
                if new_pred.confidence > 0.6:
                    event["re_forecast"] = {
                        "winner": new_pred.winner,
                        "home_score": new_pred.home_score,
                        "away_score": new_pred.away_score,
                        "confidence": new_pred.confidence,
                    }

        elif event_type == "match.finished":
            home_score = event.get("home_score", 0)
            away_score = event.get("away_score", 0)
            logger.info(f"Full time: {event['home']} {home_score}-{away_score} {event['away']}")
            if self._prediction_engine and self._state_manager:
                # Saved predictions key on the "home-away" slug (see
                # handlers/predict.py, handlers/chat.py), not the tracker's
                # provider match_id, so resolve on that same slug.
                match_id = f"{event['home'].lower()}-{event['away'].lower()}"
                await self._state_manager.resolve_match(
                    match_id, home_score, away_score,
                    home_team=event["home"], away_team=event["away"],
                    prediction_engine=self._prediction_engine,
                )

        elif event_type == "lineup.confirmed":
            logger.info(f"Lineup confirmed for {event['match_id']} ({event['team']})")

        await self.push_notifier.handle_event(event)

    async def _on_odds_swing(self, event: dict):
        logger.info(f"Odds swing {event['swing_pct']}% on {event['match_id']}")
        await self.push_notifier.handle_event(event)

    async def _on_lineup_event(self, event: dict):
        logger.info(f"Lineup: {event['team']} confirmed for {event['match_id']}")
        await self.push_notifier.handle_event(event)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> dict:
        return {
            "running": self._running,
            "matches_tracked": self.match_tracker.tracked_count,
            "matches_live": self.match_tracker.active_count,
            "odds_tracked": len(self.odds_monitor._odds),
            "lineups_tracked": len(self.lineup_watcher._lineups),
        }
