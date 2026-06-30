import unittest

from wcbot.agents.data_ingestion import DataIngestionAgent, WORLD_CUP_SPORT_KEY


class LiveTournamentDataTests(unittest.TestCase):
    def setUp(self):
        self.ingestion = DataIngestionAgent()

    def tearDown(self):
        import asyncio
        asyncio.run(self.ingestion.close())

    def test_uses_fifa_world_cup_sport_key(self):
        self.assertEqual(WORLD_CUP_SPORT_KEY, "soccer_fifa_world_cup")

    def test_normalizes_provider_team_aliases_and_market(self):
        event = self.ingestion._normalize_odds_event({
            "id": "fixture-1",
            "home_team": "USA",
            "away_team": "Bosnia & Herzegovina",
            "commence_time": "2026-07-02T00:00:00Z",
            "bookmakers": [{
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": "USA", "price": 1.5},
                        {"name": "Draw", "price": 4.0},
                        {"name": "Bosnia & Herzegovina", "price": 7.0},
                    ],
                }],
            }],
        })

        self.assertEqual(event["home_team"], "United States")
        self.assertEqual(event["away_team"], "Bosnia and Herzegovina")
        self.assertEqual(event["bookmaker_count"], 1)
        total = event["market_home_prob"] + event["market_draw_prob"] + event["market_away_prob"]
        self.assertAlmostEqual(total, 1.0)

    def test_normalizes_completed_score(self):
        event = self.ingestion._normalize_score_event({
            "id": "result-1",
            "home_team": "Ivory Coast",
            "away_team": "Norway",
            "commence_time": "2026-06-30T17:00:00Z",
            "completed": True,
            "scores": [
                {"name": "Ivory Coast", "score": "1"},
                {"name": "Norway", "score": "2"},
            ],
        })

        self.assertEqual(event["status"], "completed")
        self.assertEqual((event["home_score"], event["away_score"]), (1, 2))


if __name__ == "__main__":
    unittest.main()
