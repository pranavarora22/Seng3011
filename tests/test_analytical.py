"""Tests for the enhanced multi-factor analytical model Lambda."""

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
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(10), "Normal")

    def test_medium(self):
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(35), "Elevated")

    def test_high(self):
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(60), "Emerging Outbreak")

    def test_critical(self):
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(90), "Severe Outbreak")

    def test_boundary_low_medium(self):
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(25), "Elevated")


class TestComputeZScores(unittest.TestCase):
    """Retained class name; now covers compute_signals (replacement for compute_z_scores)."""

    def test_insufficient_data_below_threshold(self):
        """Groups with fewer than MIN_WEEKS_REQUIRED weeks get INSUFFICIENT_DATA."""
        from analytical_lambda import compute_signals, MIN_WEEKS_REQUIRED

        records = make_records(MIN_WEEKS_REQUIRED - 1)
        signals = compute_signals(records)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["payload"]["risk_level"], "INSUFFICIENT_DATA")

    def test_stable_when_all_cases_identical(self):
        """Stable baseline (std=0) still produces a valid signal, not an error."""
        from analytical_lambda import compute_signals, MIN_WEEKS_REQUIRED

        records = make_records(MIN_WEEKS_REQUIRED + 4, base=100)
        signals = compute_signals(records)

        self.assertEqual(len(signals), 1)
        self.assertIn(signals[0]["payload"]["risk_level"], ["Normal", "Elevated", "Declining"])

    def test_critical_on_large_spike(self):
        """A large spike on current week should produce a high risk_score."""
        from analytical_lambda import compute_signals

        records = [make_record("influenza", "AUS", f"{y}-W01", cases)
                   for y, cases in zip(range(2020, 2023), [50, 100, 150])]
        for i in range(2, 30):
            records.append(make_record("influenza", "AUS", f"2020-W{i:02d}", 100))
        records.append(make_record("influenza", "AUS", "2023-W01", 10000))

        signal = compute_signals(records)[0]
        self.assertGreater(signal["payload"]["risk_score"], 50)

    def test_scores_most_recent_week_only(self):
        """Only one signal per (disease, country) group."""
        from analytical_lambda import compute_signals, MIN_WEEKS_REQUIRED

        records = make_records(MIN_WEEKS_REQUIRED + 4, base=100)
        signals = compute_signals(records)

        self.assertEqual(len(signals), 1)

    def test_groups_by_disease_and_country(self):
        """Records for different countries produce separate signals."""
        from analytical_lambda import compute_signals

        records = make_records(30, base=100, country="AUS") + make_records(30, base=200, country="IND")
        signals = compute_signals(records)

        countries = {s["payload"]["country_code"] for s in signals}
        self.assertEqual(countries, {"AUS", "IND"})

    def test_output_schema(self):
        """Signal payload must contain all required fields."""
        from analytical_lambda import compute_signals, MIN_WEEKS_REQUIRED

        records = make_records(MIN_WEEKS_REQUIRED + 4, base=100)
        signal = compute_signals(records)[0]

        self.assertEqual(signal["event_type"], "PUBLIC_HEALTH_SIGNAL")
        required = {
            "disease", "country_code", "epi_week", "current_cases",
            "seasonal_mean", "seasonal_std_dev", "seasonal_z_score",
            "growth_rate", "acceleration", "persistence_weeks",
            "risk_score", "risk_level",
        }
        self.assertTrue(required.issubset(signal["payload"].keys()))


class TestParseQueryParams(unittest.TestCase):
    def test_non_integer_limit_does_not_raise(self):
        """?limit=abc must not raise ValueError — should fall back to default 100."""
        from analytical_lambda import parse_query_params

        params = parse_query_params({"queryStringParameters": {"limit": "abc"}})
        self.assertEqual(params["limit"], 100)


class TestAnalyticalLambdaHandler(unittest.TestCase):
    def test_returns_200_with_signals(self):
        """lambda_handler should return 200 and a signals list."""
        import json
        from analytical_lambda import lambda_handler, MIN_WEEKS_REQUIRED

        records = make_records(MIN_WEEKS_REQUIRED + 4, base=100)
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
        from analytical_lambda import lambda_handler, MIN_WEEKS_REQUIRED

        records = (
            make_records(MIN_WEEKS_REQUIRED + 4, base=100, disease="influenza", country="AUS")
            + make_records(MIN_WEEKS_REQUIRED + 4, base=200, disease="influenza", country="IND")
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


def make_records(n, base=100, spike=None, disease="influenza", country="AUS", start_year=2020):
    """Build n weekly records spread across years so week_of_year repeats naturally."""
    records = []
    for i in range(n):
        year = start_year + (i // 52)
        week = (i % 52) + 1
        epi_week = f"{year}-W{week:02d}"
        cases = spike if (spike is not None and i == n - 1) else base
        records.append(make_record(disease, country, epi_week, cases))
    return records


class TestRemovedLegacyFunctions(unittest.TestCase):
    def test_classify_z_score_is_removed(self):
        """classify_z_score is superseded by classify_risk_score and must not exist."""
        import analytical_lambda
        self.assertFalse(hasattr(analytical_lambda, "classify_z_score"))

    def test_compute_z_scores_is_removed(self):
        """compute_z_scores is superseded by compute_signals and must not exist."""
        import analytical_lambda
        self.assertFalse(hasattr(analytical_lambda, "compute_z_scores"))

    def test_min_records_for_zscore_is_removed(self):
        """MIN_RECORDS_FOR_ZSCORE is superseded by MIN_WEEKS_REQUIRED and must not exist."""
        import analytical_lambda
        self.assertFalse(hasattr(analytical_lambda, "MIN_RECORDS_FOR_ZSCORE"))


class TestComputeSignals(unittest.TestCase):
    def test_spike_produces_high_risk_score(self):
        """A large spike on the current week should produce a high risk_score."""
        from analytical_lambda import compute_signals

        # Prior week-1 values vary (50, 100, 150) so std > 0 and seasonal z-score fires
        records = []
        for y, cases in zip(range(2020, 2023), [50, 100, 150]):
            records.append(make_record("influenza", "AUS", f"{y}-W01", cases))
        for i in range(2, 30):
            records.append(make_record("influenza", "AUS", f"2020-W{i:02d}", 100))
        records.append(make_record("influenza", "AUS", "2023-W01", 10000))

        signal = compute_signals(records)[0]
        self.assertGreater(signal["payload"]["risk_score"], 50)

    def test_declining_after_peak(self):
        """Risk level is Declining when score drops >20pts from the prior week."""
        from analytical_lambda import compute_signals, MIN_WEEKS_REQUIRED

        records = make_records(MIN_WEEKS_REQUIRED + 2, base=100)
        records[-2]["payload"]["cases_detected"] = 5000  # big spike penultimate week
        records[-1]["payload"]["cases_detected"] = 100   # back to baseline

        signal = compute_signals(records)[0]
        self.assertEqual(signal["payload"]["risk_level"], "Declining")


    def test_insufficient_data(self):
        """Fewer than MIN_WEEKS_REQUIRED records → INSUFFICIENT_DATA."""
        from analytical_lambda import compute_signals, MIN_WEEKS_REQUIRED

        records = make_records(MIN_WEEKS_REQUIRED - 1)
        signals = compute_signals(records)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["payload"]["risk_level"], "INSUFFICIENT_DATA")

    def test_sort_uses_chronological_order_not_lexicographic(self):
        """Weeks must sort chronologically — W9 before W10, not after.

        Lexicographic: '2020-W9' > '2020-W10' → W9 treated as most-recent.
        Chronological: (2020,9) < (2020,10) → W10 correctly treated as most-recent.
        """
        from analytical_lambda import compute_signals

        # All history in 2019 so they sort before 2020 regardless of method.
        records = make_records(30, base=100, start_year=2019)
        # Append 2020-W9 (spike) then 2020-W10 (normal) — W10 must be current.
        records.append(make_record("influenza", "AUS", "2020-W9", 9999))
        records.append(make_record("influenza", "AUS", "2020-W10", 100))

        signal = compute_signals(records)[0]
        self.assertEqual(signal["payload"]["epi_week"], "2020-W10")

    def test_insufficient_data_signal_has_required_structure(self):
        """INSUFFICIENT_DATA signals must include event_id, event_type, domain."""
        from analytical_lambda import compute_signals, MIN_WEEKS_REQUIRED

        records = make_records(MIN_WEEKS_REQUIRED - 1)
        signal = compute_signals(records)[0]

        self.assertIn("event_id", signal)
        self.assertIn("event_type", signal)
        self.assertIn("domain", signal)
        self.assertEqual(signal["event_type"], "PUBLIC_HEALTH_SIGNAL")

    def test_output_schema(self):
        """Signal payload must contain all required fields."""
        from analytical_lambda import compute_signals, MIN_WEEKS_REQUIRED

        records = make_records(MIN_WEEKS_REQUIRED + 10, base=100)
        signal = compute_signals(records)[0]

        self.assertEqual(signal["event_type"], "PUBLIC_HEALTH_SIGNAL")
        self.assertEqual(signal["domain"], "HEALTH")
        required = {
            "disease", "country_code", "epi_week", "current_cases",
            "seasonal_mean", "seasonal_std_dev", "seasonal_z_score",
            "growth_rate", "acceleration", "persistence_weeks",
            "risk_score", "risk_level",
        }
        self.assertTrue(required.issubset(signal["payload"].keys()))

    def test_groups_by_disease_and_country(self):
        """Records for different countries produce separate signals."""
        from analytical_lambda import compute_signals

        records = make_records(30, base=100, country="AUS") + make_records(30, base=200, country="IND")
        signals = compute_signals(records)

        countries = {s["payload"]["country_code"] for s in signals}
        self.assertEqual(countries, {"AUS", "IND"})

    def test_seasonal_baseline_uses_same_week(self):
        """seasonal_mean must reflect only prior years' same week, not all history."""
        from analytical_lambda import compute_signals

        # Build 3 years: week 1 always has 100 cases; week 26 has 500 cases.
        # Current week is year 3 week 1 with 110 cases.
        # Seasonal mean for week 1 should be ~100, not skewed by week-26 records.
        records = []
        for year in [2021, 2022]:
            for w, cases in [(1, 100), (26, 500)]:
                records.append(make_record("influenza", "AUS", f"{year}-W{w:02d}", cases))
        # Pad to meet MIN_WEEKS_REQUIRED with neutral data
        from analytical_lambda import MIN_WEEKS_REQUIRED
        for i in range(2, MIN_WEEKS_REQUIRED):
            records.append(make_record("influenza", "AUS", f"2021-W{i+1:02d}", 100))
        # Current week
        records.append(make_record("influenza", "AUS", "2023-W01", 110))

        signal = compute_signals(records)[0]
        self.assertAlmostEqual(signal["payload"]["seasonal_mean"], 100.0, places=0)


class TestClassifyRiskScore(unittest.TestCase):
    def test_normal(self):
        """Score below 25 → Normal."""
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(10), "Normal")

    def test_elevated(self):
        """Score 25–49 → Elevated."""
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(35), "Elevated")

    def test_emerging_outbreak(self):
        """Score 50–69 → Emerging Outbreak."""
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(60), "Emerging Outbreak")

    def test_sustained_outbreak(self):
        """Score 70–84 → Sustained Outbreak."""
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(75), "Sustained Outbreak")

    def test_severe_outbreak(self):
        """Score ≥85 → Severe Outbreak."""
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(90), "Severe Outbreak")

    def test_declining(self):
        """Score dropping >20 pts from prev_score ≥25 → Declining."""
        from analytical_lambda import classify_risk_score
        self.assertEqual(classify_risk_score(30, prev_score=55), "Declining")


if __name__ == "__main__":
    unittest.main()
