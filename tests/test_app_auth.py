import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app as app_module
from processing import ensure_directories


class AppAuthTests(unittest.TestCase):
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
            "AUTH_USERS": {
                "testuser": generate_password_hash("testpass"),
                "seconduser": generate_password_hash("secondpass"),
            },
        }
        self.config_patcher = patch.dict(app_module.CONFIG, self.config, clear=False)
        self.config_patcher.start()
        ensure_directories(app_module.CONFIG)
        app_module.init_database()
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.config_patcher.stop()
        self.temp_dir.cleanup()

    def test_unauthenticated_index_redirects_to_login(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_unauthenticated_api_route_returns_401(self):
        response = self.client.get("/audit-history")

        self.assertEqual(response.status_code, 401)

    def test_login_with_wrong_credentials_shows_error(self):
        response = self.client.post("/login", data={"username": "testuser", "password": "wrong"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("invalidos", response.get_data(as_text=True))

    def test_login_with_correct_credentials_grants_access(self):
        login_response = self.client.post(
            "/login", data={"username": "testuser", "password": "testpass"}
        )
        self.assertEqual(login_response.status_code, 302)

        index_response = self.client.get("/")
        self.assertEqual(index_response.status_code, 200)

    def test_second_registered_user_can_also_login(self):
        login_response = self.client.post(
            "/login", data={"username": "seconduser", "password": "secondpass"}
        )
        self.assertEqual(login_response.status_code, 302)

        index_response = self.client.get("/")
        self.assertEqual(index_response.status_code, 200)

    def test_logout_clears_session(self):
        with self.client.session_transaction() as sess:
            sess["authenticated"] = True

        self.client.get("/logout")
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
