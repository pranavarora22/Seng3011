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


if __name__ == "__main__":
    unittest.main()
