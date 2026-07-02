import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


RUN_ID_PATTERN = re.compile(r"^\d{8}_\d{6}_[0-9a-f]{8}$")


def generate_run_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def is_valid_run_id(run_id: str) -> bool:
    return bool(run_id) and bool(RUN_ID_PATTERN.fullmatch(run_id))


def _require_valid_run_id(run_id: str) -> str:
    if not is_valid_run_id(run_id):
        raise ValueError(f"run_id invalido: {run_id!r}")
    return run_id


def get_run_dir(config: dict, run_id: str) -> Path:
    return Path(config["RUNS_DIR"]) / _require_valid_run_id(run_id)


def get_run_upload_dir(config: dict, run_id: str) -> Path:
    return Path(config["UPLOAD_DIR"]) / _require_valid_run_id(run_id)


def get_run_file_paths(config: dict, run_id: str) -> dict[str, Path]:
    run_dir = get_run_dir(config, run_id)
    return {
        "run_dir": run_dir,
        "blocklist": run_dir / "novos_dominios.txt",
        "whitelist": run_dir / "whitelist.txt",
        "report": run_dir / "relatorio.txt",
        "pending_update": run_dir / "pendente_atualizacao.json",
        "manifest": run_dir / "manifest.json",
    }


def write_run_manifest(config: dict, run_id: str, data: dict) -> Path:
    manifest_path = get_run_file_paths(config, run_id)["manifest"]
    manifest_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    return manifest_path


def read_run_manifest(config: dict, run_id: str) -> dict | None:
    manifest_path = get_run_file_paths(config, run_id)["manifest"]
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


@contextmanager
def acquire_update_lock(config: dict, timeout_seconds: float = 10.0, poll_interval: float = 0.1):
    lock_path = Path(config["BASE_UPDATE_LOCK_PATH"])
    deadline = time.monotonic() + timeout_seconds
    handle = None

    while time.monotonic() < deadline:
        try:
            handle = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(handle, str(os.getpid()).encode("ascii", errors="ignore"))
            break
        except FileExistsError:
            time.sleep(poll_interval)

    if handle is None:
        raise TimeoutError("Atualizacao de base em andamento; tente novamente em instantes")

    try:
        yield lock_path
    finally:
        try:
            os.close(handle)
        finally:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
