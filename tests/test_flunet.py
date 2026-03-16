"""Tests for WHO FluNet data fetcher."""

import os
import sys
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

    def test_fetches_lookback_years(self):
        """process_flunet_disease should call fetch_flunet_records for current and previous year."""
        from lambda_function import process_flunet_disease

        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.fetch_flunet_records", return_value=[]) as mock_fetch:
            process_flunet_disease()

        self.assertEqual(mock_fetch.call_count, 2)

    def test_skips_null_or_zero_cases(self):
        """Records with null or 0 ALL_INF must be excluded."""
        from lambda_function import process_flunet_disease

        raw = [
            {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 1, "INF_ALL": None},
            {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 2, "INF_ALL": 0},
            {"COUNTRY_CODE": "AUS", "ISO_YEAR": 2024, "ISO_WEEK": 3, "INF_ALL": 50},
        ]
        with patch("lambda_function.is_local_mock", return_value=False), \
             patch("lambda_function.fetch_flunet_records", side_effect=[raw, []]):
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
             patch("lambda_function.fetch_flunet_records", side_effect=[raw, []]):
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
    def test_handler_returns_influenza_success(self):
        """lambda_handler should call process_flunet_disease and return influenza status."""
        from lambda_function import lambda_handler
        import json

        with patch("lambda_function.process_flunet_disease", return_value=[]):
            with patch("lambda_function.save_output"):
                result = lambda_handler({}, None)

        body = json.loads(result["body"])
        self.assertIn("influenza", body)
        self.assertEqual(body["influenza"]["status"], "success")

    def test_handler_returns_error_on_exception(self):
        """lambda_handler should catch exceptions and return error status."""
        from lambda_function import lambda_handler
        import json

        with patch("lambda_function.process_flunet_disease", side_effect=RuntimeError("API down")):
            result = lambda_handler({}, None)

        body = json.loads(result["body"])
        self.assertEqual(body["influenza"]["status"], "error")
        self.assertIn("API down", body["influenza"]["message"])


if __name__ == "__main__":
    unittest.main()
