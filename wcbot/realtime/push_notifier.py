import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PushNotifier:
    def __init__(self, app=None, state_manager=None):
        self._app = app
        self._state_manager = state_manager

    async def broadcast_to_subscribers(self, team: str, message: str, parse_mode: str = "Markdown"):
        if not self._state_manager or not self._app:
            logger.warning("Notifier not wired — skipping broadcast")
            return 0

        subscribers = await self._state_manager.get_team_subscribers(team)
        sent = 0

        for user_id in subscribers:
            try:
                await self._app.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode=parse_mode,
                )
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to notify {user_id}: {e}")

        if sent:
            logger.info(f"Broadcast '{team}': {sent}/{len(subscribers)} delivered")
        return sent

    async def handle_event(self, event: dict):
        event_type = event.get("type", "")

        if event_type == "score.changed":
            await self._notify_score(event)
        elif event_type == "lineup.confirmed":
            await self._notify_lineup(event)
        elif event_type == "match.started":
            await self._notify_match_start(event)
        elif event_type == "match.finished":
            await self._notify_match_end(event)
        elif event_type == "odds.swing":
            await self._notify_odds_swing(event)

    async def _notify_score(self, event: dict):
        home = event["home"]
        away = event["away"]
        msg = (
            f"⚽ *Live Score Update*\n"
            f"{home} {event['new_home']}–{event['new_away']} {away}\n"
            f"Was: {event['old_home']}–{event['old_away']}"
        )
        for team in (home, away):
            await self.broadcast_to_subscribers(team, msg)

    async def _notify_lineup(self, event: dict):
        side = "Home" if event["team"] == "home" else "Away"
        msg = (
            f"📋 *Lineup Confirmed*\n"
            f"{side} XI announced — Formation: {event.get('formation', '?')}"
        )
        await self.broadcast_to_subscribers(f"match_{event['match_id']}", msg)

    async def _notify_match_start(self, event: dict):
        msg = (
            f"🔴 *Match Started*\n"
            f"{event['home']} vs {event['away']} is underway!"
        )
        for team in (event["home"], event["away"]):
            await self.broadcast_to_subscribers(team, msg)

    async def _notify_match_end(self, event: dict):
        msg = (
            f"🏁 *Full Time*\n"
            f"{event['home']} {event.get('home_score', 0)}–{event.get('away_score', 0)} {event['away']}"
        )
        for team in (event["home"], event["away"]):
            await self.broadcast_to_subscribers(team, msg)

    async def _notify_odds_swing(self, event: dict):
        old = event["old"]
        new = event["new"]
        msg = (
            f"📈 *Odds Movement*\n"
            f"Significant swing detected: {event['swing_pct']}%\n"
            f"Home: {old['home']} → {new['home']}\n"
            f"Draw: {old['draw']} → {new['draw']}\n"
            f"Away: {old['away']} → {new['away']}"
        )
        await self.broadcast_to_subscribers(f"odds_{event['match_id']}", msg)
