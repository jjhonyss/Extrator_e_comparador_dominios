import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
from processing import ensure_directories


class AppRouteTests(unittest.TestCase):
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
        self.csrf_headers = {"X-CSRF-Token": self.csrf_token}

    def tearDown(self):
        self.config_patcher.stop()
        self.temp_dir.cleanup()

    def test_process_requires_files(self):
        response = self.client.post(
            "/process", data={}, content_type="multipart/form-data", headers=self.csrf_headers
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Nenhum arquivo enviado")

    def test_process_txt_returns_run_summary(self):
        response = self.client.post(
            "/process",
            data={
                "files": (io.BytesIO(b"bet365.com\ninstagram.com\n"), "entrada.txt"),
            },
            content_type="multipart/form-data",
            headers=self.csrf_headers,
        )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(payload["run_id"])
        self.assertEqual(payload["blocklist"], ["bet365.com"])
        self.assertEqual(payload["whitelist"][0]["domain"], "instagram.com")

    def test_confirm_update_returns_conflict_when_locked(self):
        with patch("app.confirm_pending_update", side_effect=TimeoutError("Atualizacao de base em andamento; tente novamente em instantes")):
            response = self.client.post(
                "/confirm-update", json={"run_id": "run_teste"}, headers=self.csrf_headers
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Atualizacao de base em andamento", response.get_json()["error"])

    def test_download_base_atualizada_uses_run_id_artifact(self):
        process_response = self.client.post(
            "/process",
            data={
                "files": (io.BytesIO(b"novodominio.bet\n"), "entrada.txt"),
            },
            content_type="multipart/form-data",
            headers=self.csrf_headers,
        )
        process_payload = process_response.get_json()

        confirm_response = self.client.post(
            "/confirm-update",
            json={
                "run_id": process_payload["run_id"],
                "approved_domains": process_payload["blocklist"],
                "rejected_domains": [],
            },
            headers=self.csrf_headers,
        )

        download_response = self.client.get(f"/download/base_atualizada?run_id={process_payload['run_id']}")
        downloaded_content = download_response.get_data(as_text=True)
        download_response.close()

        self.assertEqual(process_response.status_code, 200)
        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(download_response.status_code, 200)
        self.assertIn("novodominio.bet", downloaded_content)

    def test_audit_history_returns_processed_run(self):
        self.client.post(
            "/process",
            data={
                "files": (io.BytesIO(b"bet365.com\n"), "entrada.txt"),
            },
            content_type="multipart/form-data",
            headers=self.csrf_headers,
        )

        response = self.client.get("/audit-history")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["runs"]), 1)
        self.assertEqual(len(payload["runs"][0]["files"]), 1)
        self.assertTrue(payload["runs"][0]["files"][0].endswith("entrada.txt"))


if __name__ == "__main__":
    unittest.main()
