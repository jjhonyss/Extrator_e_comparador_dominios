from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

CONFIG = {
    "MAX_FILE_SIZE": 50 * 1024 * 1024,
    "ALLOWED_EXTENSIONS": {".pdf", ".txt"},
    "BASE_FILE_PATH": BASE_DIR / "base" / "base_atual.txt",
    "WHITELIST_PATH": BASE_DIR / "output" / "whitelist.txt",
    "OUTPUT_PATH": BASE_DIR / "output" / "novos_dominios.txt",
    "REPORT_PATH": BASE_DIR / "output" / "relatorio.txt",
    "PENDING_UPDATE_PATH": BASE_DIR / "output" / "pendente_atualizacao.json",
    "UPLOAD_DIR": BASE_DIR / "uploads",
    "OUTPUT_DIR": BASE_DIR / "output",
    "AUDIT_DIR": BASE_DIR / "audits",
    "BACKUP_DIR": BASE_DIR / "backups",
    "LOG_DIR": BASE_DIR / "logs",
    "ENABLE_OCR": True,
    "OCR_ONLY_IF_NO_DOMAINS": True,
    "OCR_LANGUAGE": "por+eng",
    "AUTO_UPDATE_BASE": False,
    "BACKUP_BEFORE_UPDATE": True,
}
