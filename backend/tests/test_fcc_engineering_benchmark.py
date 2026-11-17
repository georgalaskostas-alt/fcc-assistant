"""Offline tests for the exploratory FCC benchmark runner."""
import importlib.util
from pathlib import Path
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "benchmarks" / "run_fcc_benchmark.py"
spec = importlib.util.spec_from_file_location("fcc_benchmark_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class BenchmarkRunnerTests(unittest.TestCase):
    def test_dataset_loads_with_unique_cases(self):
        cases = runner.load_cases(RUNNER.with_name("fcc_engineering_v1.json"))
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({c["id"] for c in cases}), 10)

    def test_screen_rejects_truncation(self):
        case = {"must_include": ["coke"], "must_not_claim": []}
        result = runner.screen_answer(case, "Coke burns", "length")
        self.assertFalse(result["screen_pass"])

    def test_screen_reports_missing_fragments(self):
        case = {"must_include": ["coke", "heat"], "must_not_claim": []}
        result = runner.screen_answer(case, "Coke burns", "stop")
        self.assertEqual(result["missing_keyword_fragments"], ["heat"])

    def test_screen_reports_forbidden_phrases(self):
        case = {"must_include": ["coke"], "must_not_claim": ["metals disappear"]}
        result = runner.screen_answer(case, "Coke burns; metals disappear", "stop")
        self.assertEqual(result["matched_forbidden_phrases"], ["metals disappear"])

    def test_endpoint_restricts_to_loopback(self):
        self.assertEqual(runner.validate_local_endpoint("http://127.0.0.1:18081"),
                         "http://127.0.0.1:18081")
        for url in ("https://127.0.0.1:18081", "http://example.com",
                    "http://127.0.0.1:18081/other", "http://user:pass@localhost:18081"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                runner.validate_local_endpoint(url)


if __name__ == "__main__":
    unittest.main()
