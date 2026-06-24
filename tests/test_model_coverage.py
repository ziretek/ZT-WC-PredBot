import tempfile
import unittest

from wcbot.agents.models.elo import EloModel
from wcbot.agents.models.poisson_xg import PoissonXGModel
from wcbot.data.teams import WORLD_CUP_TEAMS_2026


class ModelCoverageTests(unittest.TestCase):
    def test_all_configured_teams_have_model_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            elo = EloModel(persist_path=f"{tmpdir}/elo.json")
            poisson = PoissonXGModel(persist_path=f"{tmpdir}/poisson.json")

        self.assertEqual(set(WORLD_CUP_TEAMS_2026) - set(elo.ratings), set())
        self.assertEqual(set(WORLD_CUP_TEAMS_2026) - set(poisson.params), set())


if __name__ == "__main__":
    unittest.main()
