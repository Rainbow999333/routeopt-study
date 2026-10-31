import importlib.util
import unittest

from routeopt.evaluate import evaluate
from routeopt.models import Matrix, Scenario, Stop, coordinate_digest
from routeopt.optional_ortools import solve_ortools


@unittest.skipUnless(importlib.util.find_spec("ortools"), "optional dependency not installed")
class OptionalOrtoolsTests(unittest.TestCase):
    def setUp(self):
        self.scenario = Scenario("oracle", Stop("D", 0, 0),
                                 (Stop("A", .01, 0, 1), Stop("B", .02, 0, 1)), 1, 3)

    def matrix(self, values):
        return Matrix(("D", "A", "B"), tuple(tuple(row) for row in values),
                      {"provider": "oracle", "coordinates_sha256": coordinate_digest(self.scenario)})

    def test_small_directed_optimum(self):
        matrix = self.matrix([[0, 7000, 3000], [3000, 0, 4000], [2000, 1000, 0]])
        solution = solve_ortools(self.scenario, matrix, time_limit_s=1)
        result = evaluate(self.scenario, matrix, solution)
        self.assertTrue(result["feasible"])
        self.assertEqual(result["distance_km"], 7)

    def test_unreachable_customer_cannot_be_dropped(self):
        matrix = self.matrix([[0, None, 3000], [None, 0, None], [2000, None, 0]])
        solution = solve_ortools(self.scenario, matrix, time_limit_s=1)
        self.assertEqual(solution.status, "not_found")
        self.assertFalse(evaluate(self.scenario, matrix, solution)["feasible"])


if __name__ == "__main__":
    unittest.main()
