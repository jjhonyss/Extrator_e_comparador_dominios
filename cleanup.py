import shutil
import time
from pathlib import Path

from config import CONFIG


def is_older_than(path: Path, days: int, now: float | None = None) -> bool:
    if days < 0 or not path.exists():
        return False
    reference = time.time() if now is None else now
    age_seconds = reference - path.stat().st_mtime
    return age_seconds > days * 86400


def delete_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def cleanup_paths(paths: list[Path], days: int, now: float | None = None) -> list[str]:
    removed: list[str] = []
    for path in paths:
        if is_older_than(path, days, now=now):
            delete_path(path)
            removed.append(str(path))
    return removed


def cleanup_runtime_artifacts(config: dict, now: float | None = None) -> dict[str, list[str]]:
    runs_dir = Path(config["RUNS_DIR"])
    upload_dir = Path(config["UPLOAD_DIR"])
    backup_dir = Path(config["BACKUP_DIR"])
    output_dir = Path(config["OUTPUT_DIR"])

    return {
        "runs": cleanup_paths(list(runs_dir.glob("*")), config["RETENTION_RUN_DAYS"], now=now),
        "uploads": cleanup_paths(list(upload_dir.glob("*")), config["RETENTION_UPLOAD_DAYS"], now=now),
        "backups": cleanup_paths(list(backup_dir.glob("base_atual_*.txt")), config["RETENTION_BACKUP_DAYS"], now=now),
        "updated_bases": cleanup_paths(
            list(output_dir.glob("base_atualizada_*.txt")),
            config["RETENTION_UPDATED_BASE_DAYS"],
            now=now,
        ),
    }


if __name__ == "__main__":
    summary = cleanup_runtime_artifacts(CONFIG)
    for section, removed in summary.items():
        print(f"{section}: {len(removed)} removido(s)")
        for item in removed:
            print(f"  - {item}")
