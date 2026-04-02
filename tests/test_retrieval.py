"""Tests for the retrieval Lambda."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["LOCAL_MOCK"] = "True"

import unittest  # noqa: E402


class TestDocsRoute(unittest.TestCase):
    def test_docs_returns_200(self):
        """GET /docs must return HTTP 200."""
        from retrieval_lambda import lambda_handler

        result = lambda_handler({"rawPath": "/docs", "queryStringParameters": None}, None)
        self.assertEqual(result["statusCode"], 200)

    def test_docs_returns_html_content_type(self):
        """GET /docs must return text/html content type."""
        from retrieval_lambda import lambda_handler

        result = lambda_handler({"rawPath": "/docs", "queryStringParameters": None}, None)
        self.assertEqual(result["headers"]["Content-Type"], "text/html")

    def test_docs_body_contains_swagger_ui(self):
        """GET /docs body must contain SwaggerUIBundle (Swagger UI marker)."""
        from retrieval_lambda import lambda_handler

        result = lambda_handler({"rawPath": "/docs", "queryStringParameters": None}, None)
        self.assertIn("SwaggerUIBundle", result["body"])

    def test_docs_body_contains_api_title(self):
        """GET /docs body must reference the Retrieval API title."""
        from retrieval_lambda import lambda_handler

        result = lambda_handler({"rawPath": "/docs", "queryStringParameters": None}, None)
        self.assertIn("Retrieval", result["body"])

    def test_non_docs_path_still_queries(self):
        """Requests to paths other than /docs must still run the normal query handler."""
        import json
        from unittest.mock import patch
        from retrieval_lambda import lambda_handler

        with patch("retrieval_lambda.is_local_mock", return_value=True), \
             patch("retrieval_lambda.load_records_from_s3", return_value=[]):
            result = lambda_handler({"rawPath": "/", "queryStringParameters": None}, None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertIn("items", body)


class TestResolveCountry(unittest.TestCase):
    def test_alpha3_passthrough(self):
        """A valid 3-letter code should be returned as-is."""
        from retrieval_lambda import resolve_country
        self.assertEqual(resolve_country("AUS"), "AUS")

    def test_alpha3_case_insensitive(self):
        """Alpha-3 codes should be uppercased."""
        from retrieval_lambda import resolve_country
        self.assertEqual(resolve_country("aus"), "AUS")

    def test_alpha2_to_alpha3(self):
        """A 2-letter code like 'US' should resolve to 'USA'."""
        from retrieval_lambda import resolve_country
        self.assertEqual(resolve_country("US"), "USA")

    def test_full_name(self):
        """A full country name should resolve to alpha-3."""
        from retrieval_lambda import resolve_country
        self.assertEqual(resolve_country("australia"), "AUS")

    def test_full_name_united_states(self):
        """'United States' should resolve to 'USA'."""
        from retrieval_lambda import resolve_country
        self.assertEqual(resolve_country("United States"), "USA")

    def test_full_name_united_kingdom(self):
        """'United Kingdom' should resolve to 'GBR'."""
        from retrieval_lambda import resolve_country
        self.assertEqual(resolve_country("United Kingdom"), "GBR")

    def test_unknown_returns_uppercased(self):
        """An unrecognisable input should be returned uppercased."""
        from retrieval_lambda import resolve_country
        self.assertEqual(resolve_country("xyzzy"), "XYZZY")

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace should be stripped."""
        from retrieval_lambda import resolve_country
        self.assertEqual(resolve_country("  AUS  "), "AUS")


if __name__ == "__main__":
    unittest.main()
