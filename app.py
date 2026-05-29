import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from config import CONFIG
from domain_processing.audit import load_audit_history
from processing import (
    confirm_pending_update,
    ensure_directories,
    generate_run_id,
    get_run_file_paths,
    get_run_upload_dir,
    latest_updated_base_path,
    process_files,
)


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = CONFIG["MAX_FILE_SIZE"]


def configure_logging() -> None:
    ensure_directories(CONFIG)
    log_path = Path(CONFIG["LOG_DIR"]) / "app.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )


def init_database() -> None:
    db_path = Path(CONFIG["AUDIT_DIR"]) / "auditoria.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processing_runs (
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
        columns = {row[1] for row in conn.execute("PRAGMA table_info(processing_runs)")}
        if "run_id" not in columns:
            conn.execute("ALTER TABLE processing_runs ADD COLUMN run_id TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rejected_domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE,
                rejected_at TEXT NOT NULL,
                run_id TEXT
            )
            """
        )


def save_audit(summary: dict) -> None:
    db_path = Path(CONFIG["AUDIT_DIR"]) / "auditoria.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO processing_runs (
                run_id, created_at, files, domains_extracted, new_domains, whitelist_count,
                blocklist_count, duplicates_removed, errors, elapsed_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary.get("run_id"),
                datetime.now().isoformat(timespec="seconds"),
                json.dumps(summary["files_processed"], ensure_ascii=True),
                summary["domains_extracted"],
                summary["new_domains"],
                summary["whitelist_count"],
                summary["blocklist_count"],
                summary["duplicates_removed"],
                json.dumps(summary["errors"], ensure_ascii=True),
                summary["elapsed_seconds"],
            ),
        )


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in CONFIG["ALLOWED_EXTENSIONS"]


@app.route("/")
def index():
    return render_template("index.html", max_file_size_mb=CONFIG["MAX_FILE_SIZE"] // (1024 * 1024))


@app.route("/process", methods=["POST"])
def process_uploads():
    uploaded_files = request.files.getlist("files")
    if not uploaded_files or all(not item.filename for item in uploaded_files):
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    saved_paths: list[Path] = []
    errors: list[str] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_id = generate_run_id()
    upload_dir = get_run_upload_dir(CONFIG, run_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    for uploaded in uploaded_files:
        if not uploaded.filename:
            continue
        if not allowed_file(uploaded.filename):
            errors.append(f"Tipo nao permitido: {uploaded.filename}")
            continue

        filename = secure_filename(uploaded.filename)
        target = upload_dir / f"{timestamp}_{filename}"
        uploaded.save(target)
        saved_paths.append(target)
        logging.info("Arquivo recebido: %s", target.name)

    if not saved_paths:
        return jsonify({"error": "Nenhum arquivo valido enviado", "errors": errors}), 400

    try:
        summary = process_files(saved_paths, CONFIG, run_id)
        summary["errors"] = errors + summary["errors"]
        save_audit(summary)
        return jsonify(summary)
    except Exception as exc:
        logging.exception("Falha inesperada no processamento")
        return jsonify({"error": f"Falha inesperada no processamento: {exc}"}), 500


@app.route("/download/<name>")
def download_file(name: str):
    run_id = request.args.get("run_id")
    run_paths = get_run_file_paths(CONFIG, run_id) if run_id else {}
    allowed_downloads = {
        "novos_dominios": run_paths.get("blocklist", CONFIG["OUTPUT_PATH"]),
        "whitelist": run_paths.get("whitelist", CONFIG["WHITELIST_PATH"]),
        "relatorio": run_paths.get("report", CONFIG["REPORT_PATH"]),
    }
    path = latest_updated_base_path(CONFIG) if name == "base_atualizada" else allowed_downloads.get(name)
    if not path or not Path(path).exists():
        return jsonify({"error": "Arquivo nao encontrado"}), 404
    return send_file(path, as_attachment=True)


@app.route("/confirm-update", methods=["POST"])
def confirm_update():
    try:
        payload = request.get_json(silent=True) or {}
        run_id = payload.get("run_id")
        summary = confirm_pending_update(
            CONFIG,
            run_id=run_id,
            approved_domains=payload.get("approved_domains") if "approved_domains" in payload else None,
            rejected_domains=payload.get("rejected_domains") if "rejected_domains" in payload else None,
        )
        logging.info("Atualizacao de base confirmada: %s", summary)
        return jsonify(summary)
    except Exception as exc:
        logging.exception("Falha ao confirmar atualizacao da base")
        return jsonify({"error": f"Falha ao confirmar atualizacao da base: {exc}"}), 500


@app.route("/whitelist")
def view_whitelist():
    run_id = request.args.get("run_id")
    path = get_run_file_paths(CONFIG, run_id)["whitelist"] if run_id else Path(CONFIG["WHITELIST_PATH"])
    content = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    return jsonify({"content": content})


@app.route("/audit-history")
def audit_history():
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 500)
    except ValueError:
        limit = 100
    return jsonify({"runs": load_audit_history(Path(CONFIG["AUDIT_DIR"]), limit)})


@app.errorhandler(413)
def file_too_large(_error):
    limit = CONFIG["MAX_FILE_SIZE"] // (1024 * 1024)
    return jsonify({"error": f"Arquivo excede o limite de {limit}MB"}), 413


configure_logging()
init_database()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
