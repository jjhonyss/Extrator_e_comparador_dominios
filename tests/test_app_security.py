import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app as app_module
from processing import ensure_directories


class CsrfAndRunIdValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.config = {
            "HOST": "127.0.0.1",
            "PORT": 5000,
            "DATA_DIR": root,
            "MAX_FILE_SIZE": 2 * 1024 * 1024,
            "ALLOWED_EXTENSIONS": {".txt", ".pdf"},
            "BASE_FILE_PATH": root / "base" / "base_atual.txt",
            "REJECTED_FILE_PATH": root / "base" / "base_rejeitados.txt",
            "WHITELIST_PATH": root / "output" / "whitelist.txt",
            "OUTPUT_PATH": root / "output" / "novos_dominios.txt",
            "REPORT_PATH": root / "output" / "relatorio.txt",
            "PENDING_UPDATE_PATH": root / "output" / "pendente_atualizacao.json",
            "UPLOAD_DIR": root / "uploads",
            "OUTPUT_DIR": root / "output",
            "RUNS_DIR": root / "output" / "runs",
            "AUDIT_DIR": root / "audits",
            "BACKUP_DIR": root / "backups",
            "LOG_DIR": root / "logs",
            "BASE_UPDATE_LOCK_PATH": root / "output" / "base_update.lock",
            "ENABLE_OCR": False,
            "OCR_ONLY_IF_NO_DOMAINS": True,
            "OCR_LANGUAGE": "por+eng",
            "AUTO_UPDATE_BASE": False,
            "BACKUP_BEFORE_UPDATE": True,
        }
        self.config_patcher = patch.dict(app_module.CONFIG, self.config, clear=False)
        self.config_patcher.start()
        ensure_directories(app_module.CONFIG)
        app_module.init_database()
        self.client = app_module.app.test_client()
        self.csrf_token = "test-csrf-token"
        with self.client.session_transaction() as sess:
            sess["authenticated"] = True
            sess["csrf_token"] = self.csrf_token

    def tearDown(self):
        self.config_patcher.stop()
        self.temp_dir.cleanup()

    def test_process_without_csrf_header_is_rejected(self):
        response = self.client.post("/process", data={}, content_type="multipart/form-data")

        self.assertEqual(response.status_code, 403)

    def test_confirm_update_without_csrf_header_is_rejected(self):
        response = self.client.post("/confirm-update", json={"run_id": "any"})

        self.assertEqual(response.status_code, 403)

    def test_confirm_update_with_wrong_csrf_header_is_rejected(self):
        response = self.client.post(
            "/confirm-update", json={"run_id": "any"}, headers={"X-CSRF-Token": "token-errado"}
        )

        self.assertEqual(response.status_code, 403)

    def test_download_rejects_path_traversal_run_id(self):
        response = self.client.get("/download/novos_dominios?run_id=../../../../etc")

        self.assertEqual(response.status_code, 400)

    def test_whitelist_rejects_path_traversal_run_id(self):
        response = self.client.get("/whitelist?run_id=../../../../etc")

        self.assertEqual(response.status_code, 400)

    def test_confirm_update_rejects_path_traversal_run_id(self):
        response = self.client.post(
            "/confirm-update",
            json={"run_id": "../../../../etc"},
            headers={"X-CSRF-Token": self.csrf_token},
        )

        self.assertEqual(response.status_code, 400)

    def test_download_accepts_well_formed_run_id_with_no_artifact(self):
        response = self.client.get("/download/novos_dominios?run_id=20260101_120000_abcdef12")

        self.assertEqual(response.status_code, 404)


class LoginRateLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.config = {
            "DATA_DIR": root,
            "BASE_FILE_PATH": root / "base" / "base_atual.txt",
            "REJECTED_FILE_PATH": root / "base" / "base_rejeitados.txt",
            "WHITELIST_PATH": root / "output" / "whitelist.txt",
            "OUTPUT_PATH": root / "output" / "novos_dominios.txt",
            "REPORT_PATH": root / "output" / "relatorio.txt",
            "PENDING_UPDATE_PATH": root / "output" / "pendente_atualizacao.json",
            "UPLOAD_DIR": root / "uploads",
            "OUTPUT_DIR": root / "output",
            "RUNS_DIR": root / "output" / "runs",
            "AUDIT_DIR": root / "audits",
            "BACKUP_DIR": root / "backups",
            "LOG_DIR": root / "logs",
            "BASE_UPDATE_LOCK_PATH": root / "output" / "base_update.lock",
            "AUTH_USERS": {"testuser": generate_password_hash("testpass")},
            "LOGIN_MAX_ATTEMPTS": 3,
            "LOGIN_LOCKOUT_MINUTES": 15,
        }
        self.config_patcher = patch.dict(app_module.CONFIG, self.config, clear=False)
        self.config_patcher.start()
        ensure_directories(app_module.CONFIG)
        app_module.init_database()
        self.client = app_module.app.test_client()
        app_module.clear_login_attempts("testuser")

    def tearDown(self):
        app_module.clear_login_attempts("testuser")
        self.config_patcher.stop()
        self.temp_dir.cleanup()

    def test_third_failed_attempt_still_shows_invalid_credentials(self):
        for _ in range(3):
            response = self.client.post("/login", data={"username": "testuser", "password": "wrong"})
            self.assertEqual(response.status_code, 200)

    def test_fourth_attempt_is_rate_limited_even_with_correct_password(self):
        for _ in range(3):
            self.client.post("/login", data={"username": "testuser", "password": "wrong"})

        response = self.client.post("/login", data={"username": "testuser", "password": "testpass"})

        self.assertEqual(response.status_code, 429)
        self.assertIn("Muitas tentativas", response.get_data(as_text=True))

    def test_successful_login_clears_previous_failed_attempts(self):
        self.client.post("/login", data={"username": "testuser", "password": "wrong"})
        self.client.post("/login", data={"username": "testuser", "password": "wrong"})

        success_response = self.client.post(
            "/login", data={"username": "testuser", "password": "testpass"}
        )
        self.assertEqual(success_response.status_code, 302)

        self.client.get("/logout")
        next_response = self.client.post(
            "/login", data={"username": "testuser", "password": "wrong"}
        )
        self.assertEqual(next_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
