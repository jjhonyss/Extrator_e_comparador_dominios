import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from domain_processing.audit import load_audit_history


class AuditHistoryTests(unittest.TestCase):
    def test_load_audit_history_returns_recent_runs_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_dir = Path(tmp) / "audits"
            audit_dir.mkdir()

            db_path = audit_dir / "auditoria.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE processing_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT,
                        created_at TEXT NOT NULL,
                        files TEXT NOT NULL,
                        domains_extracted INTEGER NOT NULL,
                        new_domains INTEGER NOT NULL,
                        whitelist_count INTEGER NOT NULL,
                        blocklist_count INTEGER NOT NULL,
                        duplicates_removed INTEGER NOT NULL,
                        errors TEXT NOT NULL,
                        elapsed_seconds REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO processing_runs (
                        run_id, created_at, files, domains_extracted, new_domains,
                        whitelist_count, blocklist_count, duplicates_removed, errors,
                        elapsed_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "run_1",
                        "2026-05-29T10:00:00",
                        json.dumps(["a.txt"]),
                        10,
                        4,
                        1,
                        3,
                        2,
                        json.dumps([]),
                        0.5,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO processing_runs (
                        run_id, created_at, files, domains_extracted, new_domains,
                        whitelist_count, blocklist_count, duplicates_removed, errors,
                        elapsed_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "run_2",
                        "2026-05-29T11:00:00",
                        json.dumps(["b.pdf"]),
                        20,
                        7,
                        2,
                        5,
                        6,
                        json.dumps(["aviso"]),
                        1.25,
                    ),
                )
                conn.commit()

            runs = load_audit_history(audit_dir)

        self.assertEqual([run["run_id"] for run in runs], ["run_2", "run_1"])
        self.assertEqual(runs[0]["files"], ["b.pdf"])
        self.assertEqual(runs[0]["errors"], ["aviso"])


if __name__ == "__main__":
    unittest.main()
