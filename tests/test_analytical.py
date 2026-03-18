"""Tests for the z-score analytical model Lambda."""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["LOCAL_MOCK"] = "True"

import unittest


def make_record(disease, country, epi_week, cases):
    return {
        "event_id": f"{disease}-{country}-{epi_week}",
        "timestamp": "2025-01-01T00:00:00+00:00",
        "event_type": "PUBLIC_HEALTH_RECORD",
        "domain": "HEALTH",
        "payload": {
            "disease": disease,
            "country_code": country,
            "epi_week": epi_week,
            "cases_detected": cases,
        },
    }


class TestClassifyZScore(unittest.TestCase):
    def test_low(self):
        from analytical_lambda import classify_z_score
        self.assertEqual(classify_z_score(0.5), "LOW")

    def test_medium(self):
        from analytical_lambda import classify_z_score
        self.assertEqual(classify_z_score(1.5), "MEDIUM")

    def test_high(self):
        from analytical_lambda import classify_z_score
        self.assertEqual(classify_z_score(2.5), "HIGH")

    def test_critical(self):
        from analytical_lambda import classify_z_score
        self.assertEqual(classify_z_score(3.0), "CRITICAL")

    def test_boundary_low_medium(self):
        from analytical_lambda import classify_z_score
        self.assertEqual(classify_z_score(1.0), "MEDIUM")


class TestComputeZScores(unittest.TestCase):
    def _make_records(self, n, base=100, spike=None):
        """Build n weekly records for AUS influenza; optionally spike the last week."""
        records = []
        for i in range(n):
            week = f"2025-W{i + 1:02d}"
            cases = spike if (spike and i == n - 1) else base
            records.append(make_record("influenza", "AUS", week, cases))
        return records

    def test_insufficient_data_below_threshold(self):
        """Groups with fewer than MIN_RECORDS_FOR_ZSCORE weeks get INSUFFICIENT_DATA."""
        from analytical_lambda import compute_z_scores, MIN_RECORDS_FOR_ZSCORE

        records = self._make_records(MIN_RECORDS_FOR_ZSCORE - 1)
        signals = compute_z_scores(records)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["payload"]["risk_level"], "INSUFFICIENT_DATA")
        self.assertIsNone(signals[0]["payload"]["z_score"])

    def test_stable_when_all_cases_identical(self):
        """If all case counts are the same, std dev is 0 → STABLE."""
        from analytical_lambda import compute_z_scores

        records = self._make_records(10, base=100)
        signals = compute_z_scores(records)

        self.assertEqual(signals[0]["payload"]["risk_level"], "STABLE")
        self.assertEqual(signals[0]["payload"]["z_score"], 0.0)

    def test_critical_on_large_spike(self):
        """A large spike in the most recent week should produce CRITICAL risk."""
        from analytical_lambda import compute_z_scores

        records = self._make_records(10, base=100, spike=10000)
        signals = compute_z_scores(records)

        self.assertEqual(signals[0]["payload"]["risk_level"], "CRITICAL")
        self.assertGreaterEqual(signals[0]["payload"]["z_score"], 3.0)

    def test_scores_most_recent_week_only(self):
        """Only the most recent epi_week per group should appear in output."""
        from analytical_lambda import compute_z_scores

        records = self._make_records(10, base=100, spike=500)
        signals = compute_z_scores(records)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["payload"]["epi_week"], "2025-W10")

    def test_groups_by_disease_and_country(self):
        """Records for different countries produce separate signals."""
        from analytical_lambda import compute_z_scores

        aus = self._make_records(10, base=100)
        ind = [make_record("influenza", "IND", f"2025-W{i+1:02d}", 200) for i in range(10)]
        signals = compute_z_scores(aus + ind)

        countries = {s["payload"]["country_code"] for s in signals}
        self.assertEqual(countries, {"AUS", "IND"})

    def test_output_schema(self):
        """Signal records must include all required payload fields."""
        from analytical_lambda import compute_z_scores

        records = self._make_records(10, base=100, spike=500)
        signal = compute_z_scores(records)[0]

        self.assertEqual(signal["event_type"], "PUBLIC_HEALTH_SIGNAL")
        self.assertEqual(signal["domain"], "HEALTH")
        required = {
            "disease", "country_code", "epi_week", "current_cases",
            "historical_mean", "historical_std_dev", "z_score", "risk_level",
        }
        self.assertTrue(required.issubset(signal["payload"].keys()))


class TestAnalyticalLambdaHandler(unittest.TestCase):
    def test_returns_200_with_signals(self):
        """lambda_handler should return 200 and a signals list."""
        import json
        from analytical_lambda import lambda_handler

        records = [make_record("influenza", "AUS", f"2025-W{i+1:02d}", 100) for i in range(10)]
        with patch("analytical_lambda.load_records", return_value=records):
            result = lambda_handler({"queryStringParameters": {"disease": "influenza"}}, None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertIn("signals", body)
        self.assertIn("count", body)

    def test_missing_disease_data_returns_error_entry(self):
        """If no records exist for a disease, response includes an error entry."""
        import json
        from analytical_lambda import lambda_handler

        with patch("analytical_lambda.load_records", return_value=[]):
            result = lambda_handler({"queryStringParameters": {"disease": "rsv"}}, None)

        body = json.loads(result["body"])
        self.assertTrue(any("error" in s for s in body["signals"]))

    def test_country_filter_applied(self):
        """country_code query param must filter signals to matching country only."""
        import json
        from analytical_lambda import lambda_handler

        records = (
            [make_record("influenza", "AUS", f"2025-W{i+1:02d}", 100) for i in range(10)]
            + [make_record("influenza", "IND", f"2025-W{i+1:02d}", 200) for i in range(10)]
        )
        with patch("analytical_lambda.load_records", return_value=records):
            result = lambda_handler(
                {"queryStringParameters": {"disease": "influenza", "country_code": "AUS"}},
                None,
            )

        body = json.loads(result["body"])
        countries = {s["payload"]["country_code"] for s in body["signals"] if "payload" in s}
        self.assertEqual(countries, {"AUS"})


class TestAnalyticalDocsRoute(unittest.TestCase):
    def test_docs_returns_200(self):
        """GET /docs must return HTTP 200."""
        from analytical_lambda import lambda_handler

        result = lambda_handler({"rawPath": "/docs", "queryStringParameters": None}, None)
        self.assertEqual(result["statusCode"], 200)

    def test_docs_returns_html_content_type(self):
        """GET /docs must return text/html content type."""
        from analytical_lambda import lambda_handler

        result = lambda_handler({"rawPath": "/docs", "queryStringParameters": None}, None)
        self.assertEqual(result["headers"]["Content-Type"], "text/html")

    def test_docs_body_contains_swagger_ui(self):
        """GET /docs body must contain SwaggerUIBundle."""
        from analytical_lambda import lambda_handler

        result = lambda_handler({"rawPath": "/docs", "queryStringParameters": None}, None)
        self.assertIn("SwaggerUIBundle", result["body"])

    def test_non_docs_path_still_returns_signals(self):
        """Requests to paths other than /docs must still run the normal signals handler."""
        import json
        from unittest.mock import patch
        from analytical_lambda import lambda_handler

        with patch("analytical_lambda.load_records", return_value=[]):
            result = lambda_handler({"rawPath": "/", "queryStringParameters": {"disease": "influenza"}}, None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertIn("signals", body)


if __name__ == "__main__":
    unittest.main()
