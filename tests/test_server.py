#!/usr/bin/env python3
"""Unit and integration test suite for server.py.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from unittest.mock import patch, MagicMock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server
from server import Config, RateLimiter, WorkshopServer, WorkshopRequestHandler


class TestConfigAndRateLimiter(unittest.TestCase):
    """Test configuration loading and rate limiter logic."""

    def test_default_config(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = Config(cli_port=9999, cli_host="127.0.0.1")
            self.assertEqual(cfg.port, 9999)
            self.assertEqual(cfg.host, "127.0.0.1")
            self.assertFalse(cfg.is_configured)

    def test_configured_api_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-proj-1234567890abcdef"}, clear=True):
            cfg = Config()
            self.assertTrue(cfg.is_configured)

    def test_placeholder_api_key_is_not_configured(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "your_api_key_here"}, clear=True):
            cfg = Config()
            self.assertFalse(cfg.is_configured)

    def test_rate_limiter_window(self):
        limiter = RateLimiter(limit=3, window_seconds=1.0)
        # 3 requests allowed
        self.assertTrue(limiter.allow()[0])
        self.assertTrue(limiter.allow()[0])
        self.assertTrue(limiter.allow()[0])
        # 4th rejected
        allowed, count, retry_after = limiter.allow()
        self.assertFalse(allowed)
        self.assertEqual(count, 3)
        self.assertGreater(retry_after, 0.0)

        # Wait for window reset
        time.sleep(1.05)
        self.assertTrue(limiter.allow()[0])


class TestServerEndpoints(unittest.TestCase):
    """Integration tests running against an in-memory HTTP server."""

    @classmethod
    def setUpClass(cls):
        # Bind to port 0 (ephemeral port assigned by OS)
        cls.config = Config(cli_port=0, cli_host="127.0.0.1")
        cls.config.api_key = "sk-test-mock-key-12345"
        cls.config.max_requests_per_hour = 5
        cls.workshop_app = WorkshopServer(cls.config)

        class TestBoundHandler(WorkshopRequestHandler):
            server_app = cls.workshop_app

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), TestBoundHandler)
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _get(self, path: str, headers: dict | None = None) -> tuple[int, dict | str, dict]:
        req = urllib.request.Request(f"{self.base_url}{path}", headers=headers or {})
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                hdrs = dict(resp.headers)
                try:
                    return status, json.loads(body), hdrs
                except Exception:
                    return status, body, hdrs
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                return e.code, json.loads(body), dict(e.headers)
            except Exception:
                return e.code, body, dict(e.headers)

    def _post(self, path: str, data: dict, headers: dict | None = None) -> tuple[int, dict | str, dict]:
        body_bytes = json.dumps(data).encode("utf-8")
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(f"{self.base_url}{path}", data=body_bytes, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                hdrs = dict(resp.headers)
                try:
                    return status, json.loads(body), hdrs
                except Exception:
                    return status, body, hdrs
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                return e.code, json.loads(body), dict(e.headers)
            except Exception:
                return e.code, body, dict(e.headers)

    def test_serve_index_html(self):
        status, body, hdrs = self._get("/")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("text/html", hdrs.get("Content-Type", ""))
        self.assertIn("Своя мастерская", body)

    def test_serve_initial_profile_json(self):
        status, body, hdrs = self._get("/initial-profile.json")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("application/json", hdrs.get("Content-Type", ""))
        self.assertEqual(body.get("schemaVersion"), 3)

    def test_serve_robots_txt(self):
        status, body, hdrs = self._get("/robots.txt")
        self.assertEqual(status, HTTPStatus.OK)

    def test_serve_nonexistent_file(self):
        status, body, _ = self._get("/nonexistent-file-404.xyz")
        self.assertEqual(status, HTTPStatus.NOT_FOUND)

    def test_directory_traversal_blocked(self):
        status, body, _ = self._get("/../../etc/passwd")
        # Should be forbidden or not found
        self.assertIn(status, (HTTPStatus.FORBIDDEN, HTTPStatus.NOT_FOUND))

    def test_cors_options(self):
        req = urllib.request.Request(f"{self.base_url}/api/health", method="OPTIONS")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, HTTPStatus.NO_CONTENT)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    def test_health_endpoint(self):
        status, body, _ = self._get("/api/health")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(body.get("app"), "svoya-masterskaya")
        self.assertEqual(body.get("configured"), True)
        self.assertTrue(len(body.get("sessionToken", "")) > 16)

    def test_propose_rejects_missing_token(self):
        status, body, _ = self._post("/api/propose", {"message": "Test"})
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)
        self.assertIn("токен", body.get("error", "").lower())

    def test_propose_rejects_wrong_token(self):
        status, body, _ = self._post(
            "/api/propose",
            {"message": "Test"},
            headers={"X-Workshop-Token": "invalid-token-here"}
        )
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)

    def test_propose_rejects_unconfigured_server(self):
        token = self.workshop_app.session_token
        # Temporarily deconfigure key
        original_key = self.workshop_app.config.api_key
        try:
            self.workshop_app.config.api_key = ""
            status, body, _ = self._post(
                "/api/propose",
                {"message": "Подготовь план по дереву"},
                headers={"X-Workshop-Token": token}
            )
            self.assertEqual(status, HTTPStatus.BAD_REQUEST)
            self.assertIn("OPENAI_API_KEY", body.get("error", ""))
        finally:
            self.workshop_app.config.api_key = original_key

    def test_propose_success_with_mocked_openai(self):
        token = self.workshop_app.session_token

        mock_proposal = {
            "version": 1,
            "id": "p-mock-1",
            "baseRevision": 0,
            "summary": "Тестовый ответ",
            "questions": [],
            "operations": []
        }

        mock_openai_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(mock_proposal),
                        "role": "assistant"
                    }
                }
            ]
        }

        mock_http_response = MagicMock()
        mock_http_response.read.return_value = json.dumps(mock_openai_response).encode("utf-8")
        mock_http_response.__enter__.return_value = mock_http_response

        real_urlopen = urllib.request.urlopen

        def custom_urlopen(req, *args, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "api.openai.com" in url:
                return mock_http_response
            return real_urlopen(req, *args, **kwargs)

        with patch("urllib.request.urlopen", side_effect=custom_urlopen):
            status, body, _ = self._post(
                "/api/propose",
                {
                    "mode": "expand",
                    "scope": "wood",
                    "message": "Расширить каталог деревянных изделий",
                    "context": {"revision": 0}
                },
                headers={"X-Workshop-Token": token}
            )

            self.assertEqual(status, HTTPStatus.OK)
            self.assertIn("proposal", body)
            self.assertEqual(body["proposal"]["id"], "p-mock-1")

    def test_propose_openai_refusal(self):
        token = self.workshop_app.session_token

        mock_openai_response = {
            "choices": [
                {
                    "message": {
                        "refusal": "I cannot provide safety critical measurements",
                        "role": "assistant"
                    }
                }
            ]
        }

        mock_http_response = MagicMock()
        mock_http_response.read.return_value = json.dumps(mock_openai_response).encode("utf-8")
        mock_http_response.__enter__.return_value = mock_http_response

        real_urlopen = urllib.request.urlopen

        def custom_urlopen(req, *args, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "api.openai.com" in url:
                return mock_http_response
            return real_urlopen(req, *args, **kwargs)

        with patch("urllib.request.urlopen", side_effect=custom_urlopen):
            status, body, _ = self._post(
                "/api/propose",
                {
                    "mode": "expand",
                    "scope": "wood",
                    "message": "Тест отказа",
                    "context": {"revision": 0}
                },
                headers={"X-Workshop-Token": token}
            )

            self.assertEqual(status, HTTPStatus.BAD_REQUEST)
            self.assertIn("отклонила", str(body.get("error", "")).lower())

    def test_propose_openai_api_error_401(self):
        token = self.workshop_app.session_token

        error_body = json.dumps({"error": {"message": "Incorrect API key provided"}}).encode("utf-8")
        http_error = urllib.error.HTTPError(
            url="https://api.openai.com/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=error_body))
        )

        real_urlopen = urllib.request.urlopen

        def custom_urlopen(req, *args, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "api.openai.com" in url:
                raise http_error
            return real_urlopen(req, *args, **kwargs)

        with patch("urllib.request.urlopen", side_effect=custom_urlopen):
            status, body, _ = self._post(
                "/api/propose",
                {
                    "mode": "expand",
                    "scope": "wood",
                    "message": "Тест 401",
                    "context": {"revision": 0}
                },
                headers={"X-Workshop-Token": token}
            )

            self.assertEqual(status, HTTPStatus.UNAUTHORIZED)
            self.assertIn("ключ", str(body.get("error", "")).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
