import os
import tempfile
import unittest
from unittest.mock import Mock

from wcbot.agents.prediction_engine import PredictionEngineAgent


class ResultSyncTests(unittest.TestCase):
    def test_completed_results_are_synced_once(self):
        engine = PredictionEngineAgent()
        engine.resolve_match = Mock()
        matches = [{
            "id": "match-1",
            "home_team": "Ivory Coast",
            "away_team": "Norway",
            "home_score": 1,
            "away_score": 2,
            "status": "completed",
        }]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "processed.json")
            self.assertEqual(engine.sync_completed_matches(matches, path), 1)
            self.assertEqual(engine.sync_completed_matches(matches, path), 0)

        engine.resolve_match.assert_called_once_with("Ivory Coast", "Norway", 1, 2)


if __name__ == "__main__":
    unittest.main()
