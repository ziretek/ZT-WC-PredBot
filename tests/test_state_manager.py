import asyncio
import os
import tempfile
import unittest

from wcbot.agents.state_manager import StateManagerAgent
from wcbot.models.prediction import Prediction


class StateManagerPersistenceTests(unittest.TestCase):
    def test_state_survives_reload_and_resolve_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "state.db")

            state = StateManagerAgent(db_path=db_path)
            asyncio.run(state.create_user(42, "zire", "Zire"))
            asyncio.run(state.add_subscription(42, "Brazil"))
            prediction = Prediction(
                prediction_id="pred-1",
                user_id=42,
                match_id="brazil-argentina",
                home_team="Brazil",
                away_team="Argentina",
                predicted_home_score=2,
                predicted_away_score=1,
                predicted_winner="Brazil",
                confidence=0.82,
                model_version="test",
            )
            asyncio.run(state.save_prediction(42, prediction.match_id, prediction))
            state.close()

            reloaded = StateManagerAgent(db_path=db_path)
            user = asyncio.run(reloaded.get_user(42))
            history = asyncio.run(reloaded.get_prediction_history(42))
            subscribers = asyncio.run(reloaded.get_team_subscribers("Brazil"))

            self.assertEqual(user.total_predictions, 1)
            self.assertEqual(len(history), 1)
            self.assertEqual(subscribers, [42])

            asyncio.run(reloaded.resolve_match("brazil-argentina", 2, 1))
            asyncio.run(reloaded.resolve_match("brazil-argentina", 2, 1))
            resolved_user = asyncio.run(reloaded.get_user(42))
            resolved_history = asyncio.run(reloaded.get_prediction_history(42))
            self.assertEqual(resolved_user.points, 5)
            self.assertEqual(resolved_user.correct_predictions, 1)
            self.assertTrue(resolved_history[0].was_correct)
            reloaded.close()

            final_reload = StateManagerAgent(db_path=db_path)
            final_user = asyncio.run(final_reload.get_user(42))
            self.assertEqual(final_user.points, 5)
            self.assertEqual(final_user.correct_predictions, 1)
            final_reload.close()


if __name__ == "__main__":
    unittest.main()
