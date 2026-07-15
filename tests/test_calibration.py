import math
import unittest

from wcbot.agents.prediction_engine import PredictionEngineAgent


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = PredictionEngineAgent()
        self.engine._calibration = {"total": 0, "correct": 0, "brier": 0.0, "log_loss": 0.0, "by_band": {}}
        self.engine._save_calibration = lambda: None

    def test_correct_high_confidence_pick_scores_low_error(self):
        self.engine.log_feedback("p1", True, confidence=0.9)

        self.assertEqual(self.engine._calibration["total"], 1)
        self.assertEqual(self.engine._calibration["correct"], 1)
        self.assertAlmostEqual(self.engine._calibration["brier"], 0.01)
        self.assertAlmostEqual(self.engine._calibration["log_loss"], -math.log(0.9))

    def test_incorrect_high_confidence_pick_scores_high_error(self):
        self.engine.log_feedback("p1", False, confidence=0.9)

        self.assertAlmostEqual(self.engine._calibration["brier"], 0.81)
        self.assertAlmostEqual(self.engine._calibration["log_loss"], -math.log(0.1))

    def test_brier_and_log_loss_are_running_means_not_sums(self):
        self.engine.log_feedback("p1", True, confidence=0.9)
        self.engine.log_feedback("p2", False, confidence=0.9)

        self.assertEqual(self.engine._calibration["total"], 2)
        self.assertAlmostEqual(self.engine._calibration["brier"], (0.01 + 0.81) / 2)
        expected_log_loss = (-math.log(0.9) + -math.log(0.1)) / 2
        self.assertAlmostEqual(self.engine._calibration["log_loss"], expected_log_loss)

    def test_feedback_buckets_into_matching_confidence_band(self):
        self.engine.log_feedback("p1", True, confidence=0.82)

        self.assertEqual(self.engine._calibration["by_band"]["80-90%"], {"total": 1, "correct": 1})


if __name__ == "__main__":
    unittest.main()
