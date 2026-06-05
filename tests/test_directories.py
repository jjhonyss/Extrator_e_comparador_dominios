import tempfile
import unittest
from pathlib import Path

from processing import ensure_directories


class DirectorySetupTests(unittest.TestCase):
    def test_ensure_directories_creates_operational_parents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "UPLOAD_DIR": root / "storage" / "uploads",
                "OUTPUT_DIR": root / "storage" / "output",
                "RUNS_DIR": root / "storage" / "output" / "runs",
                "AUDIT_DIR": root / "storage" / "audits",
                "BACKUP_DIR": root / "storage" / "backups",
                "LOG_DIR": root / "storage" / "logs",
                "BASE_FILE_PATH": root / "state" / "base" / "base_atual.txt",
                "REJECTED_FILE_PATH": root / "state" / "base" / "base_rejeitados.txt",
                "WHITELIST_PATH": root / "state" / "output" / "whitelist.txt",
                "OUTPUT_PATH": root / "state" / "output" / "novos_dominios.txt",
                "REPORT_PATH": root / "state" / "output" / "relatorio.txt",
                "PENDING_UPDATE_PATH": root / "state" / "output" / "pendente_atualizacao.json",
                "BASE_UPDATE_LOCK_PATH": root / "state" / "locks" / "base_update.lock",
            }

            ensure_directories(config)

            self.assertTrue(config["UPLOAD_DIR"].exists())
            self.assertTrue(config["OUTPUT_DIR"].exists())
            self.assertTrue(config["RUNS_DIR"].exists())
            self.assertTrue(config["AUDIT_DIR"].exists())
            self.assertTrue(config["BACKUP_DIR"].exists())
            self.assertTrue(config["LOG_DIR"].exists())
            self.assertTrue(config["BASE_FILE_PATH"].exists())
            self.assertTrue(config["REJECTED_FILE_PATH"].exists())
            self.assertTrue(config["WHITELIST_PATH"].parent.exists())
            self.assertTrue(config["OUTPUT_PATH"].parent.exists())
            self.assertTrue(config["REPORT_PATH"].parent.exists())
            self.assertTrue(config["PENDING_UPDATE_PATH"].parent.exists())
            self.assertTrue(config["BASE_UPDATE_LOCK_PATH"].parent.exists())


if __name__ == "__main__":
    unittest.main()
