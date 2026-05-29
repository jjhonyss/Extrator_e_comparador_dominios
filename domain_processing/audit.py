import json
import sqlite3
from contextlib import closing
from pathlib import Path


def parse_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def load_audit_history(audit_dir: Path, limit: int = 100) -> list[dict]:
    db_path = Path(audit_dir) / "auditoria.db"
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                id, run_id, created_at, files, domains_extracted, new_domains,
                whitelist_count, blocklist_count, duplicates_removed, errors,
                elapsed_seconds
            FROM processing_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "files": parse_json_list(row["files"]),
            "domains_extracted": row["domains_extracted"],
            "new_domains": row["new_domains"],
            "whitelist_count": row["whitelist_count"],
            "blocklist_count": row["blocklist_count"],
            "duplicates_removed": row["duplicates_removed"],
            "errors": parse_json_list(row["errors"]),
            "elapsed_seconds": row["elapsed_seconds"],
        }
        for row in rows
    ]
