import unittest

from wcbot.handlers.predict import _is_round_of_32_request


class PredictIntentTests(unittest.TestCase):
    def test_round_of_32_phrases(self):
        self.assertTrue(_is_round_of_32_request("round of 32"))
        self.assertTrue(_is_round_of_32_request("Predict R32"))
        self.assertTrue(_is_round_of_32_request("next round"))
        self.assertTrue(_is_round_of_32_request("knockout stage"))

    def test_match_prediction_is_not_round_of_32(self):
        self.assertFalse(_is_round_of_32_request("Brazil vs Argentina"))


if __name__ == "__main__":
    unittest.main()
