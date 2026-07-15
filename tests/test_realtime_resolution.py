import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from wcbot.realtime.engine import RealtimeEngine


class RealtimeMatchResolutionTests(unittest.TestCase):
    def test_match_finished_resolves_via_state_manager_with_slug_match_id(self):
        state_manager = Mock()
        state_manager.resolve_match = AsyncMock()
        prediction_engine = Mock()

        engine = RealtimeEngine(
            app=None, data_ingestion=None,
            state_manager=state_manager, prediction_engine=prediction_engine,
        )

        event = {
            "type": "match.finished",
            "match_id": "provider-fixture-999",
            "home": "Brazil",
            "away": "Argentina",
            "home_score": 2,
            "away_score": 1,
        }
        asyncio.run(engine._on_match_event(event))

        state_manager.resolve_match.assert_awaited_once_with(
            "brazil-argentina", 2, 1,
            home_team="Brazil", away_team="Argentina",
            prediction_engine=prediction_engine,
        )


if __name__ == "__main__":
    unittest.main()
