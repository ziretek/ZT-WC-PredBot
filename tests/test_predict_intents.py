import unittest
import asyncio

from wcbot.handlers.chat import ASK_FOLLOWUP, handle_predict_request
from wcbot.handlers.tournament import is_round_of_32_request


class _FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_markdown(self, text, **kwargs):
        self.replies.append(text)
        return self


class _FakeUpdate:
    def __init__(self):
        self.message = _FakeMessage()


class _FakeIngestion:
    async def fetch_world_cup_events(self):
        return []

    async def fetch_world_cup_scores(self):
        return []


class _FakeEngine:
    llm = None


class _FakeContext:
    bot_data = {
        "data_ingestion": _FakeIngestion(),
        "prediction_engine": _FakeEngine(),
    }


class PredictIntentTests(unittest.TestCase):
    def test_round_of_32_phrases(self):
        self.assertTrue(is_round_of_32_request("round of 32"))
        self.assertTrue(is_round_of_32_request("Predict R32"))
        self.assertTrue(is_round_of_32_request("next round"))
        self.assertTrue(is_round_of_32_request("knockout stage"))

    def test_match_prediction_is_not_round_of_32(self):
        self.assertFalse(is_round_of_32_request("Brazil vs Argentina"))

    def test_chat_predict_round_of_32_uses_round_handler(self):
        update = _FakeUpdate()
        result = asyncio.run(handle_predict_request(update, _FakeContext(), "Predict round of 32"))

        self.assertEqual(result, ASK_FOLLOWUP)
        self.assertIn("Round of 32", update.message.replies[-1])
        self.assertNotIn("Which match", update.message.replies[-1])


if __name__ == "__main__":
    unittest.main()
