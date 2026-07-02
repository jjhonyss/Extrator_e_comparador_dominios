import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def env_text(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser() if value and value.strip() else default


def env_extensions(name: str, default: set[str]) -> set[str]:
    value = os.getenv(name)
    if not value or not value.strip():
        return default

    extensions = {
        item if item.startswith(".") else f".{item}"
        for item in (part.strip().lower() for part in value.split(","))
        if item
    }
    return extensions or default


def env_users(name: str) -> dict[str, str]:
    value = os.getenv(name)
    if not value or not value.strip():
        return {}

    users = {}
    for entry in value.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        username, password_hash = entry.split(":", 1)
        username = username.strip()
        password_hash = password_hash.strip()
        if username and password_hash:
            users[username] = password_hash
    return users


DATA_DIR = env_path("DOMAIN_GUARD_DATA_DIR", BASE_DIR)
OUTPUT_DIR = env_path("DOMAIN_GUARD_OUTPUT_DIR", DATA_DIR / "output")

CONFIG = {
    "HOST": env_text("DOMAIN_GUARD_HOST", "127.0.0.1"),
    "PORT": env_int("DOMAIN_GUARD_PORT", 5000),
    "DATA_DIR": DATA_DIR,
    "MAX_FILE_SIZE": env_int("DOMAIN_GUARD_MAX_FILE_SIZE", 500 * 1024 * 1024),
    "ALLOWED_EXTENSIONS": env_extensions("DOMAIN_GUARD_ALLOWED_EXTENSIONS", {".pdf", ".txt"}),
    "BASE_FILE_PATH": env_path("DOMAIN_GUARD_BASE_FILE_PATH", DATA_DIR / "base" / "base_atual.txt"),
    "TARGET_CORRECTIONS_PATH": env_path("DOMAIN_GUARD_TARGET_CORRECTIONS_PATH", DATA_DIR / "base" / "correcoes_manuais.txt"),
    "REJECTED_FILE_PATH": env_path("DOMAIN_GUARD_REJECTED_FILE_PATH", DATA_DIR / "base" / "base_rejeitados.txt"),
    "WHITELIST_PATH": env_path("DOMAIN_GUARD_WHITELIST_PATH", OUTPUT_DIR / "whitelist.txt"),
    "OUTPUT_PATH": env_path("DOMAIN_GUARD_OUTPUT_PATH", OUTPUT_DIR / "novos_dominios.txt"),
    "REPORT_PATH": env_path("DOMAIN_GUARD_REPORT_PATH", OUTPUT_DIR / "relatorio.txt"),
    "PENDING_UPDATE_PATH": env_path("DOMAIN_GUARD_PENDING_UPDATE_PATH", OUTPUT_DIR / "pendente_atualizacao.json"),
    "UPLOAD_DIR": env_path("DOMAIN_GUARD_UPLOAD_DIR", DATA_DIR / "uploads"),
    "OUTPUT_DIR": OUTPUT_DIR,
    "RUNS_DIR": env_path("DOMAIN_GUARD_RUNS_DIR", OUTPUT_DIR / "runs"),
    "AUDIT_DIR": env_path("DOMAIN_GUARD_AUDIT_DIR", DATA_DIR / "audits"),
    "BACKUP_DIR": env_path("DOMAIN_GUARD_BACKUP_DIR", DATA_DIR / "backups"),
    "LOG_DIR": env_path("DOMAIN_GUARD_LOG_DIR", DATA_DIR / "logs"),
    "BASE_UPDATE_LOCK_PATH": env_path("DOMAIN_GUARD_BASE_UPDATE_LOCK_PATH", OUTPUT_DIR / "base_update.lock"),
    "ENABLE_OCR": env_bool("DOMAIN_GUARD_ENABLE_OCR", True),
    "OCR_ONLY_IF_NO_DOMAINS": env_bool("DOMAIN_GUARD_OCR_ONLY_IF_NO_DOMAINS", True),
    "OCR_LANGUAGE": env_text("DOMAIN_GUARD_OCR_LANGUAGE", "por+eng"),
    "AUTO_UPDATE_BASE": env_bool("DOMAIN_GUARD_AUTO_UPDATE_BASE", False),
    "BACKUP_BEFORE_UPDATE": env_bool("DOMAIN_GUARD_BACKUP_BEFORE_UPDATE", True),
    "RETENTION_RUN_DAYS": env_int("DOMAIN_GUARD_RETENTION_RUN_DAYS", 30),
    "RETENTION_UPLOAD_DAYS": env_int("DOMAIN_GUARD_RETENTION_UPLOAD_DAYS", 14),
    "RETENTION_BACKUP_DAYS": env_int("DOMAIN_GUARD_RETENTION_BACKUP_DAYS", 90),
    "RETENTION_UPDATED_BASE_DAYS": env_int("DOMAIN_GUARD_RETENTION_UPDATED_BASE_DAYS", 30),
    "AUTH_USERS": env_users("DOMAIN_GUARD_AUTH_USERS"),
    "SECRET_KEY": env_text("DOMAIN_GUARD_SECRET_KEY", ""),
    "SESSION_HOURS": env_int("DOMAIN_GUARD_SESSION_HOURS", 8),
    "SESSION_COOKIE_SECURE": env_bool("DOMAIN_GUARD_SESSION_COOKIE_SECURE", True),
    "LOGIN_MAX_ATTEMPTS": env_int("DOMAIN_GUARD_LOGIN_MAX_ATTEMPTS", 3),
    "LOGIN_LOCKOUT_MINUTES": env_int("DOMAIN_GUARD_LOGIN_LOCKOUT_MINUTES", 15),
}
