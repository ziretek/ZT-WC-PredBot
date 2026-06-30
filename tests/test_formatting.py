import unittest

from wcbot.models.prediction import EnsembleBreakdown, PredictionResult
from wcbot.utils.formatting import format_tentative_prediction


class FormattingTests(unittest.TestCase):
    def test_tentative_prediction_includes_pick_and_thresholds(self):
        result = PredictionResult(
            winner="Brazil",
            home_score=2,
            away_score=1,
            confidence=0.58,
            ensemble_breakdown=EnsembleBreakdown({}, {}, {}, {}, {}),
            key_factors=[],
            reasoning="Brazil have a narrow model edge.",
            model_version="test",
            low_consensus=True,
            abstained=True,
        )

        text = format_tentative_prediction(result, "Brazil", "Argentina", 3, 0.55)

        self.assertIn("Prediction (low confidence)", text)
        self.assertIn("Brazil (2–1)", text)
        self.assertIn("55%", text)
        self.assertIn("low", text.lower())


if __name__ == "__main__":
    unittest.main()
