import os
import tempfile
import time
import unittest
from pathlib import Path

from cleanup import cleanup_runtime_artifacts


class CleanupTests(unittest.TestCase):
    def test_cleanup_runtime_artifacts_removes_only_old_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / "output" / "runs"
            uploads_dir = root / "uploads"
            backups_dir = root / "backups"
            output_dir = root / "output"
            runs_dir.mkdir(parents=True)
            uploads_dir.mkdir(parents=True)
            backups_dir.mkdir(parents=True)

            old_run = runs_dir / "run_old"
            new_run = runs_dir / "run_new"
            old_upload = uploads_dir / "upload_old"
            old_backup = backups_dir / "base_atual_20260101_000000.txt"
            old_updated_base = output_dir / "base_atualizada_20260101_000000.txt"
            preserved_base = root / "base" / "base_atual.txt"

            old_run.mkdir()
            new_run.mkdir()
            old_upload.mkdir()
            old_backup.write_text("backup", encoding="utf-8")
            old_updated_base.write_text("updated", encoding="utf-8")
            preserved_base.parent.mkdir(parents=True)
            preserved_base.write_text("base", encoding="utf-8")

            now = time.time()
            old_timestamp = now - (40 * 86400)
            recent_timestamp = now - 3600
            for path in (old_run, old_upload, old_backup, old_updated_base):
                path.touch()
                os.utime(path, (old_timestamp, old_timestamp))
            os.utime(new_run, (recent_timestamp, recent_timestamp))

            summary = cleanup_runtime_artifacts(
                {
                    "RUNS_DIR": runs_dir,
                    "UPLOAD_DIR": uploads_dir,
                    "BACKUP_DIR": backups_dir,
                    "OUTPUT_DIR": output_dir,
                    "RETENTION_RUN_DAYS": 30,
                    "RETENTION_UPLOAD_DAYS": 14,
                    "RETENTION_BACKUP_DAYS": 30,
                    "RETENTION_UPDATED_BASE_DAYS": 30,
                },
                now=now,
            )

            self.assertFalse(old_run.exists())
            self.assertTrue(new_run.exists())
            self.assertFalse(old_upload.exists())
            self.assertFalse(old_backup.exists())
            self.assertFalse(old_updated_base.exists())
            self.assertTrue(preserved_base.exists())
            self.assertEqual(len(summary["runs"]), 1)
            self.assertEqual(len(summary["uploads"]), 1)
            self.assertEqual(len(summary["backups"]), 1)
            self.assertEqual(len(summary["updated_bases"]), 1)


if __name__ == "__main__":
    unittest.main()
