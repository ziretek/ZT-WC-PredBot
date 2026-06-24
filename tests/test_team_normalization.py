import unittest

from wcbot.utils.teams import normalize_team_name


class TeamNormalizationTests(unittest.TestCase):
    def test_common_aliases(self):
        self.assertEqual(normalize_team_name("USA"), "United States")
        self.assertEqual(normalize_team_name("usmnt"), "United States")
        self.assertEqual(normalize_team_name("Korea Republic"), "South Korea")
        self.assertEqual(normalize_team_name("Cote d'Ivoire"), "Ivory Coast")
        self.assertEqual(normalize_team_name("Curacao"), "Curaçao")

    def test_unknown_team_returns_none(self):
        self.assertIsNone(normalize_team_name("Atlantis FC"))


if __name__ == "__main__":
    unittest.main()
