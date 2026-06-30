import unittest

from wcbot.agents.prediction_engine import PredictionEngineAgent


class PredictionThresholdTests(unittest.TestCase):
    def setUp(self):
        self.engine = PredictionEngineAgent()

    def test_three_model_consensus_with_meaningful_edge_is_official(self):
        self.assertFalse(self.engine._should_abstain("Brazil", 0.55, 3))

    def test_low_edge_remains_tentative(self):
        self.assertTrue(self.engine._should_abstain("Brazil", 0.54, 4))

    def test_draw_remains_tentative(self):
        self.assertTrue(self.engine._should_abstain("Draw", 0.70, 4))


if __name__ == "__main__":
    unittest.main()
