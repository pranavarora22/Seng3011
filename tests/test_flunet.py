"""Tests for WHO FluNet data fetcher."""

import os
import sys
from itertools import chain, repeat
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["LOCAL_MOCK"] = "True"

import unittest


class TestFetchFlunetRecords(unittest.TestCase):
    def test_returns_list_of_dicts(self):
        """fetch_flunet_records should return a list of dicts from the API value array."""
        from lambda_function import fetch_flunet_records

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "value": [
                {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 4, "ALL_INF": 142},
            ]
        }

        with patch("requests.get", return_value=mock_response):
            records = fetch_flunet_records(2024)

        self.assertIsInstance(records, list)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["ISO_WEEK"], 4)


class TestProcessFlunetDisease(unittest.TestCase):
    def test_local_mock_skips_http(self):
        """In LOCAL_MOCK mode with no fixture, should return [] without calling fetch."""
        from lambda_function import process_flunet_disease

        fixture = os.path.join("tests", "mock_s3", "raw-data", "influenza_who.json")
        assert not os.path.exists(fixture), "Remove fixture before running this test"

        with patch("lambda_function.fetch_flunet_records") as mock_fetch:
            records = process_flunet_disease()
            mock_fetch.assert_not_called()

        self.assertEqual(records, [])

    def test_fetches_all_years_from_start_year(self):
        """process_flunet_disease should fetch every year from start_year up to current year."""
        from lambda_function import process_flunet_disease, DISEASE_CONFIG
        from datetime import datetime, timezone

        start_year = DISEASE_CONFIG["influenza"]["start_year"]
        current_year = datetime.now(timezone.utc).year
        expected_calls = current_year - start_year + 1

        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.fetch_odata_records", return_value=[]) as mock_fetch:
            process_flunet_disease()

        self.assertEqual(mock_fetch.call_count, expected_calls)

    def test_skips_null_or_zero_cases(self):
        """Records with null or 0 ALL_INF must be excluded."""
        from lambda_function import process_flunet_disease

        raw = [
            {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 1, "INF_ALL": None},
            {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 2, "INF_ALL": 0},
            {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 3, "INF_ALL": 50},
        ]
        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.fetch_odata_records", side_effect=chain([raw], repeat([]))):
            records = process_flunet_disease()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["payload"]["cases_detected"], 50)

    def test_builds_correct_schema(self):
        """process_flunet_disease should return records with country_code + epi_week schema."""
        from lambda_function import process_flunet_disease

        raw = [
            {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 4, "INF_ALL": 142},
        ]
        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.fetch_odata_records", side_effect=chain([raw], repeat([]))):
            records = process_flunet_disease()

        self.assertGreater(len(records), 0)
        r = records[0]
        self.assertEqual(r["event_type"], "PUBLIC_HEALTH_RECORD")
        self.assertEqual(r["domain"], "HEALTH")
        self.assertIn("country_code", r["payload"])
        self.assertIn("epi_week", r["payload"])
        self.assertIn("cases_detected", r["payload"])
        self.assertEqual(r["payload"]["disease"], "influenza")
        self.assertNotIn("state", r["payload"])


class TestNoLegacyCode(unittest.TestCase):
    def test_no_month_map(self):
        """MONTH_MAP is dead code and must not exist in the module."""
        import lambda_function
        self.assertFalse(hasattr(lambda_function, "MONTH_MAP"))

    def test_no_csv_processors(self):
        """CSV-based processors are dead code and must not exist in the module."""
        import lambda_function
        self.assertFalse(hasattr(lambda_function, "PROCESSORS"))

    def test_no_csv_helper_functions(self):
        """CSV helper functions are dead code and must not exist in the module."""
        import lambda_function
        dead = ["find_header_row", "read_csv", "resolve_column",
                "normalize_state", "build_records", "distribute_annual_to_weeks",
                "process_date_column_disease", "process_year_month_disease",
                "process_year_only_disease"]
        for name in dead:
            self.assertFalse(hasattr(lambda_function, name), f"{name} should not exist")


class TestSaveOutput(unittest.TestCase):
    def test_local_mock_writes_to_disk(self):
        """save_output in LOCAL_MOCK mode should write JSON file to local clean path."""
        import json
        import tempfile
        from lambda_function import save_output

        with tempfile.TemporaryDirectory() as tmp:
            with patch("lambda_function.is_local_mock", return_value=True), \
                 patch("lambda_function.LOCAL_CLEAN_PATH", tmp):
                save_output("influenza", [{"event_id": "test"}])

            written = os.path.join(tmp, "influenza_clean.json")
            self.assertTrue(os.path.exists(written))
            with open(written) as f:
                data = json.load(f)
            self.assertEqual(data[0]["event_id"], "test")

    def test_s3_upload_called_when_not_local_mock(self):
        """save_output outside LOCAL_MOCK mode should put object to S3."""
        from lambda_function import save_output

        mock_s3 = MagicMock()
        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.S3_BUCKET", "test-bucket"), \
             patch("boto3.client", return_value=mock_s3):
            save_output("influenza", [])

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        self.assertEqual(call_kwargs["Bucket"], "test-bucket")
        self.assertIn("influenza_clean.json", call_kwargs["Key"])


class TestLambdaHandler(unittest.TestCase):
    def test_handler_returns_all_three_diseases(self):
        """lambda_handler must return status for influenza, rsv, and sars-cov-2."""
        import json
        from lambda_function import lambda_handler

        with patch("lambda_function.process_disease", return_value=[]), \
             patch("lambda_function.save_output"):
            result = lambda_handler({}, None)

        body = json.loads(result["body"])
        self.assertIn("influenza", body)
        self.assertIn("rsv", body)
        self.assertIn("sars-cov-2", body)
        for disease in ("influenza", "rsv", "sars-cov-2"):
            self.assertEqual(body[disease]["status"], "success")

    def test_handler_returns_error_on_exception(self):
        """lambda_handler should catch exceptions and return error status."""
        import json
        from lambda_function import lambda_handler

        def fail_influenza(disease_name, config):
            if disease_name == "influenza":
                raise RuntimeError("API down")
            return []

        with patch("lambda_function.process_disease", side_effect=fail_influenza), \
             patch("lambda_function.save_output"):
            result = lambda_handler({}, None)

        body = json.loads(result["body"])
        self.assertEqual(body["influenza"]["status"], "error")
        self.assertIn("API down", body["influenza"]["message"])

    def test_handler_one_disease_error_does_not_abort_others(self):
        """If one disease fails, the others must still be attempted."""
        import json
        from lambda_function import lambda_handler

        def fail_rsv(disease_name, config):
            if disease_name == "rsv":
                raise RuntimeError("RSV API down")
            return []

        with patch("lambda_function.process_disease", side_effect=fail_rsv), \
             patch("lambda_function.save_output"):
            result = lambda_handler({}, None)

        body = json.loads(result["body"])
        self.assertEqual(body["rsv"]["status"], "error")
        self.assertEqual(body["influenza"]["status"], "success")
        self.assertEqual(body["sars-cov-2"]["status"], "success")


class TestDiseaseConfig(unittest.TestCase):
    def test_rsv_in_disease_config(self):
        """DISEASE_CONFIG must include rsv."""
        import lambda_function
        self.assertIn("rsv", lambda_function.DISEASE_CONFIG)

    def test_sars_cov2_in_disease_config(self):
        """DISEASE_CONFIG must include sars-cov-2."""
        import lambda_function
        self.assertIn("sars-cov-2", lambda_function.DISEASE_CONFIG)

    def test_sars_cov2_uses_ncov_endpoint(self):
        """sars-cov-2 config must use the NCOV OData service."""
        import lambda_function
        endpoint = lambda_function.DISEASE_CONFIG["sars-cov-2"]["endpoint"]
        self.assertIn("NCOV", endpoint)

    def test_sars_cov2_uses_covid_style(self):
        """sars-cov-2 must use covid style so REPORT_DATE is parsed for epi_week."""
        import lambda_function
        self.assertEqual(lambda_function.DISEASE_CONFIG["sars-cov-2"]["style"], "covid")

    def test_rsv_uses_viwfnt_endpoint(self):
        """rsv must use VIW_FNT — RSV field is in the same table as influenza."""
        import lambda_function
        endpoint = lambda_function.DISEASE_CONFIG["rsv"]["endpoint"]
        self.assertIn("VIW_FNT", endpoint)


class TestProcessDisease(unittest.TestCase):
    def test_rsv_local_mock_no_fixture_returns_empty(self):
        """process_disease('rsv') in LOCAL_MOCK with no fixture returns []."""
        from lambda_function import process_disease, DISEASE_CONFIG

        # Patch LOCAL_RAW_PATH to a temp dir that has no fixture file
        with patch("lambda_function.is_local_mock", return_value=True), \
             patch("lambda_function.LOCAL_RAW_PATH", "/tmp/no-such-dir"):
            records = process_disease("rsv", DISEASE_CONFIG["rsv"])

        self.assertEqual(records, [])

    def test_rsv_builds_correct_schema(self):
        """process_disease('rsv') normalises RSV rows to the project schema."""
        from lambda_function import process_disease, DISEASE_CONFIG

        raw = [{"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 5, "RSV": 80}]
        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.fetch_odata_records", side_effect=chain([raw], repeat([]))):
            records = process_disease("rsv", DISEASE_CONFIG["rsv"])

        self.assertEqual(len(records), 1)
        r = records[0]
        self.assertEqual(r["event_type"], "PUBLIC_HEALTH_RECORD")
        self.assertEqual(r["payload"]["disease"], "rsv")
        self.assertEqual(r["payload"]["country_code"], "AUS")
        self.assertEqual(r["payload"]["epi_week"], "2024-W05")
        self.assertEqual(r["payload"]["cases_detected"], 80)

    def test_sars_cov2_builds_correct_schema(self):
        """process_disease('sars-cov-2') normalises NCOV rows using REPORT_DATE + ISO3."""
        from lambda_function import process_disease, DISEASE_CONFIG
        from datetime import datetime, timezone

        current_year = datetime.now(timezone.utc).year
        raw = [{"ISO3": "AUS", "REPORT_DATE": f"{current_year}-01-28", "COVID_NEW_CASES": 500}]
        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.fetch_covid_records", return_value=raw):
            records = process_disease("sars-cov-2", DISEASE_CONFIG["sars-cov-2"])

        self.assertEqual(len(records), 1)
        r = records[0]
        self.assertEqual(r["payload"]["disease"], "sars-cov-2")
        self.assertEqual(r["payload"]["country_code"], "AUS")
        self.assertEqual(r["payload"]["cases_detected"], 500)

    def test_rsv_skips_zero_cases(self):
        """RSV rows with zero or null cases must be excluded."""
        from lambda_function import process_disease, DISEASE_CONFIG

        raw = [
            {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 1, "RSV": None},
            {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 2, "RSV": 0},
            {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 3, "RSV": 40},
        ]
        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.fetch_odata_records", side_effect=chain([raw], repeat([]))):
            records = process_disease("rsv", DISEASE_CONFIG["rsv"])

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["payload"]["cases_detected"], 40)

    def test_sars_cov2_stores_all_historical_records(self):
        """process_disease('sars-cov-2') must keep ALL rows regardless of age."""
        from lambda_function import process_disease, DISEASE_CONFIG
        from datetime import datetime, timezone

        current_year = datetime.now(timezone.utc).year
        old_year = current_year - 5  # previously outside lookback window, now kept

        raw = [
            {"ISO3": "AUS", "REPORT_DATE": f"{old_year}-06-01", "COVID_NEW_CASES": 999},
            {"ISO3": "AUS", "REPORT_DATE": f"{current_year}-01-15", "COVID_NEW_CASES": 100},
        ]
        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.fetch_covid_records", return_value=raw):
            records = process_disease("sars-cov-2", DISEASE_CONFIG["sars-cov-2"])

        self.assertEqual(len(records), 2)

    def test_sars_cov2_skips_zero_cases(self):
        """SARS-CoV-2 rows with zero or null cases must be excluded."""
        from lambda_function import process_disease, DISEASE_CONFIG

        from datetime import datetime, timezone
        yr = datetime.now(timezone.utc).year
        raw = [
            {"ISO3": "AUS", "REPORT_DATE": f"{yr}-01-01", "COVID_NEW_CASES": None},
            {"ISO3": "AUS", "REPORT_DATE": f"{yr}-01-08", "COVID_NEW_CASES": 0},
            {"ISO3": "AUS", "REPORT_DATE": f"{yr}-01-15", "COVID_NEW_CASES": 200},
        ]
        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.fetch_covid_records", return_value=raw):
            records = process_disease("sars-cov-2", DISEASE_CONFIG["sars-cov-2"])

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["payload"]["cases_detected"], 200)


class TestFetchCovidRecords(unittest.TestCase):
    def test_fetches_without_year_filter(self):
        """fetch_covid_records must call the endpoint with no OData $filter."""
        from lambda_function import fetch_covid_records

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"value": [{"ISO3": "AUS"}]}

        with patch("requests.get", return_value=mock_response) as mock_get:
            fetch_covid_records("https://example.com/NCOV/TABLE")

        called_url = mock_get.call_args[0][0]
        self.assertNotIn("$filter", called_url)
        self.assertNotIn("ISO_YEAR", called_url)


class TestIso2ToIso3(unittest.TestCase):
    def test_au_maps_to_aus(self):
        import lambda_function
        self.assertEqual(lambda_function.ISO2_TO_ISO3.get("AU"), "AUS")

    def test_us_maps_to_usa(self):
        import lambda_function
        self.assertEqual(lambda_function.ISO2_TO_ISO3.get("US"), "USA")

    def test_gb_maps_to_gbr(self):
        import lambda_function
        self.assertEqual(lambda_function.ISO2_TO_ISO3.get("GB"), "GBR")


if __name__ == "__main__":
    unittest.main()
