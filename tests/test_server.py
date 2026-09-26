#!/usr/bin/env python3
"""Unit and integration test suite for server.py.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
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
        with patch.dict(os.environ, {}, clear=True), patch("server.load_env_file", return_value={}):
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
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.config = Config(cli_port=0, cli_host="127.0.0.1", data_dir=pathlib.Path(cls.temp_dir.name))
        cls.config.api_key = "sk-test-mock-key-12345"
        cls.config.access_key = ""
        cls.config.public_api = False
        cls.config.max_requests_per_hour = 20
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
        cls.temp_dir.cleanup()

    def setUp(self):
        # Reset storage between tests
        if self.config.data_dir.is_dir():
            for p in self.config.data_dir.glob("*"):
                if p.is_file():
                    try:
                        p.unlink()
                    except OSError:
                        pass
        if self.config.backups_dir.is_dir():
            for p in self.config.backups_dir.glob("*"):
                if p.is_file():
                    try:
                        p.unlink()
                    except OSError:
                        pass

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

    def test_private_files_are_not_served(self):
        for path in ("/.env", "/.env.example", "/server.py", "/src/app.js", "/src/seed.json", "/.git/config", "/README_RU.md"):
            status, _, _ = self._get(path)
            self.assertEqual(status, HTTPStatus.NOT_FOUND, path)

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

    def test_no_permissive_cors(self):
        status, _, hdrs = self._get("/api/health")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertNotIn("Access-Control-Allow-Origin", hdrs)

    def test_public_host_without_access_key_gets_no_token(self):
        status, body, _ = self._get("/api/health", headers={"Host": "tree.example.org"})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(body["accessRequired"])
        self.assertFalse(body["accessGranted"])
        self.assertEqual(body["sessionToken"], "")
        status, body, _ = self._post(
            "/api/propose",
            {"message": "Test"},
            headers={"Host": "tree.example.org", "X-Workshop-Token": self.workshop_app.session_token},
        )
        self.assertEqual(status, HTTPStatus.FORBIDDEN)

    def test_access_key_unlocks_public_host(self):
        self.config.access_key = "door-key-123"
        try:
            status, body, _ = self._get("/api/health", headers={"Host": "tree.example.org"})
            self.assertFalse(body["accessGranted"])
            status, body, _ = self._get("/api/health", headers={"Host": "tree.example.org", "X-Workshop-Key": "wrong"})
            self.assertFalse(body["accessGranted"])
            status, body, _ = self._get("/api/health", headers={"Host": "tree.example.org", "X-Workshop-Key": "door-key-123"})
            self.assertTrue(body["accessGranted"])
            self.assertEqual(body["sessionToken"], self.workshop_app.session_token)
            # With a key configured even localhost must present it
            status, body, _ = self._get("/api/health")
            self.assertFalse(body["accessGranted"])
        finally:
            self.config.access_key = ""

    def test_public_api_opens_public_host(self):
        self.config.public_api = True
        try:
            status, body, _ = self._get("/api/health", headers={"Host": "tree.example.org"})
            self.assertFalse(body["accessRequired"])
            self.assertTrue(body["accessGranted"])
            self.assertEqual(body["sessionToken"], self.workshop_app.session_token)
        finally:
            self.config.public_api = False

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
            if "/chat/completions" in url:
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

    def test_propose_skills_mode_forbids_questions(self):
        token = self.workshop_app.session_token
        sent = []
        mock_http_response = MagicMock()
        mock_http_response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": json.dumps({"summary": "s", "allocations": [], "newSkills": []}), "role": "assistant"}}]}
        ).encode("utf-8")
        mock_http_response.__enter__.return_value = mock_http_response
        real_urlopen = urllib.request.urlopen

        def custom_urlopen(req, *args, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "/chat/completions" in url:
                sent.append(json.loads(req.data))
                return mock_http_response
            return real_urlopen(req, *args, **kwargs)

        with patch("urllib.request.urlopen", side_effect=custom_urlopen):
            for mode in ("skills", "expand"):
                status, _, _ = self._post(
                    "/api/propose",
                    {"mode": mode, "scope": "all", "message": "Собрал полку", "context": {"revision": 0}},
                    headers={"X-Workshop-Token": token},
                )
                self.assertEqual(status, HTTPStatus.OK)

        skills_system = [m["content"] for m in sent[0]["messages"] if m["role"] == "system"]
        expand_system = [m["content"] for m in sent[1]["messages"] if m["role"] == "system"]
        self.assertEqual(skills_system, [server.SKILLS_MODE_RULES])
        self.assertIn("Никогда не задавай вопросов", server.SKILLS_MODE_RULES)
        self.assertEqual(sent[0]["response_format"]["json_schema"]["schema"], self.workshop_app.suggest_schemas["skills"])
        self.assertNotIn("baseRevision", sent[0]["response_format"]["json_schema"]["schema"]["properties"])
        self.assertEqual(expand_system, [self.workshop_app.ai_rules])

    def test_propose_project_mode_uses_own_schema(self):
        token = self.workshop_app.session_token
        sent = []
        answer = {"summary": "s", "branchIds": ["wood"], "skillIds": [], "newSkills": [], "steps": [], "checks": [],
                  "toolIds": [], "stage": 1, "risk": "care", "size": "Выходные"}
        mock_http_response = MagicMock()
        mock_http_response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": json.dumps(answer), "role": "assistant"}}]}
        ).encode("utf-8")
        mock_http_response.__enter__.return_value = mock_http_response

        real_urlopen = urllib.request.urlopen

        def custom_urlopen(req, *args, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "/chat/completions" in url:
                sent.append(json.loads(req.data))
                return mock_http_response
            return real_urlopen(req, *args, **kwargs)

        with patch("urllib.request.urlopen", side_effect=custom_urlopen):
            status, body, _ = self._post(
                "/api/propose",
                {"mode": "project", "scope": "all", "message": "Полка для книг", "context": {"revision": 3}},
                headers={"X-Workshop-Token": token},
            )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(body["proposal"], answer)
        self.assertEqual(sent[0]["messages"][0]["content"], server.PROJECT_MODE_RULES)
        self.assertEqual(sent[0]["response_format"]["json_schema"]["name"], "project_suggestion")
        self.assertEqual(sent[0]["response_format"]["json_schema"]["schema"], self.workshop_app.suggest_schemas["project"])

    def test_suggest_schemas_are_strict_and_modes_complete(self):
        from src.build import check_strict_schema

        self.assertEqual(set(self.workshop_app.suggest_schemas), set(server.SUGGEST_MODES))
        for schema in self.workshop_app.suggest_schemas.values():
            check_strict_schema(schema)

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
            if "/chat/completions" in url:
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
            if "/chat/completions" in url:
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

    def test_save_flow_and_backups(self):
        # 1. GET /api/save initially returns exists: False
        status, body, _ = self._get("/api/save")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertFalse(body.get("exists"))

        # 2. POST /api/save with valid state
        sample_state = {
            "schemaVersion": 4,
            "revision": 1,
            "branches": [{"id": "wood", "title": "Дерево"}],
            "skills": [{"id": "saw", "branchId": "wood", "title": "Пиление"}],
            "events": [],
            "projects": [],
            "tools": [],
            "inventory": {},
            "mastery": {},
            "notes": {},
            "goals": {},
            "audit": [],
            "settings": {"theme": "light"}
        }
        status, post_body, _ = self._post("/api/save", {"state": sample_state, "note": "rev 1 test"})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(post_body.get("ok"))
        self.assertEqual(post_body.get("revision"), 1)
        self.assertTrue(post_body.get("backupFile"))

        # 3. GET /api/save now returns exists: True with saved state
        status, get_body, _ = self._get("/api/save")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(get_body.get("exists"))
        self.assertEqual(get_body.get("revision"), 1)
        self.assertEqual(get_body["save"]["state"]["skills"][0]["id"], "saw")

        # 4. Save revision 2
        sample_state["revision"] = 2
        sample_state["skills"].append({"id": "plane", "branchId": "wood", "title": "Строгание"})
        status, post_body2, _ = self._post("/api/save", {"state": sample_state, "note": "rev 2 test"})
        self.assertEqual(status, HTTPStatus.OK)
        backup2_file = post_body2.get("backupFile")

        # 5. GET /api/backups returns both backups and git info
        status, backups_body, _ = self._get("/api/backups")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertGreaterEqual(backups_body.get("totalBackups", 0), 2)
        self.assertIn("git", backups_body)

        # 6. POST /api/restore to restore revision 1 backup
        first_backup = post_body.get("backupFile")
        status, restore_body, _ = self._post("/api/restore", {"filename": first_backup})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(restore_body.get("ok"))
        self.assertEqual(restore_body["save"]["state"]["revision"], 1)

        # Verify current save is now revision 1
        status, get_restored, _ = self._get("/api/save")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(get_restored.get("revision"), 1)

    def test_save_invalid_payload_rejected(self):
        # Empty body or missing required state
        status, body, _ = self._post("/api/save", {"invalid": True})
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

        # Missing schemaVersion in state
        status, body, _ = self._post("/api/save", {"state": {"foo": "bar"}})
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    def test_restore_invalid_filename_rejected(self):
        # Directory traversal attempt
        status, body, _ = self._post("/api/restore", {"filename": "../../../etc/passwd"})
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

        # Nonexistent backup
        status, body, _ = self._post("/api/restore", {"filename": "save_999999_rev999.json"})
        self.assertEqual(status, HTTPStatus.NOT_FOUND)

    def test_manual_backup_endpoint(self):
        sample_state = {
            "schemaVersion": 4,
            "revision": 10,
            "branches": [{"id": "wood", "title": "Дерево"}],
            "skills": [{"id": "saw", "branchId": "wood", "title": "Пиление"}],
            "events": [],
            "projects": [],
            "tools": [],
            "inventory": {},
            "mastery": {},
            "notes": {},
            "goals": {},
            "audit": [],
            "settings": {"theme": "light"}
        }
        # First ensure a save exists
        self._post("/api/save", {"state": sample_state, "note": "prep manual backup"})
        status, body, _ = self._post("/api/backup", {})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(body.get("ok"))
        self.assertTrue(body.get("backupFile"))

    def test_git_commit_endpoint(self):
        sample_state = {
            "schemaVersion": 4,
            "revision": 20,
            "branches": [{"id": "wood", "title": "Дерево"}],
            "skills": [{"id": "saw", "branchId": "wood", "title": "Пиление"}],
            "events": [],
            "projects": [],
            "tools": [],
            "inventory": {},
            "mastery": {},
            "notes": {},
            "goals": {},
            "audit": [],
            "settings": {"theme": "light"}
        }
        # First ensure a save exists
        self._post("/api/save", {"state": sample_state, "note": "prep git commit"})
        status, body, _ = self._post("/api/git-commit", {"message": "Тестовый коммит"})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(body.get("ok"))
        self.assertIn("git", body)

    def test_save_endpoints_access_control(self):
        self.config.access_key = "secret-save-key"
        try:
            # Without key from public host -> 403
            status, _, _ = self._get("/api/save", headers={"Host": "public.example.com"})
            self.assertEqual(status, HTTPStatus.FORBIDDEN)

            status, _, _ = self._post("/api/save", {"state": {}}, headers={"Host": "public.example.com"})
            self.assertEqual(status, HTTPStatus.FORBIDDEN)

            status, _, _ = self._get("/api/backups", headers={"Host": "public.example.com"})
            self.assertEqual(status, HTTPStatus.FORBIDDEN)

            # With correct key -> allowed
            status, body, _ = self._get("/api/save", headers={"Host": "public.example.com", "X-Workshop-Key": "secret-save-key"})
            self.assertEqual(status, HTTPStatus.OK)
        finally:
            self.config.access_key = ""


if __name__ == "__main__":
    unittest.main(verbosity=2)
