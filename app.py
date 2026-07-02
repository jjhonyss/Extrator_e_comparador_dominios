import json
import logging
import secrets
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash
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
    run_updated_base_path,
)


_runtime_initialized = False

_login_attempts: dict[str, list[float]] = {}
_login_attempts_lock = threading.Lock()


class RuntimeConfigError(RuntimeError):
    pass


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
    with closing(sqlite3.connect(db_path)) as conn:
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
        conn.commit()


def validate_runtime_settings() -> None:
    if CONFIG["PORT"] < 1 or CONFIG["PORT"] > 65535:
        raise RuntimeConfigError("Configuracao invalida: DOMAIN_GUARD_PORT deve estar entre 1 e 65535")
    if CONFIG["MAX_FILE_SIZE"] <= 0:
        raise RuntimeConfigError("Configuracao invalida: DOMAIN_GUARD_MAX_FILE_SIZE deve ser maior que zero")
    if not CONFIG["ALLOWED_EXTENSIONS"]:
        raise RuntimeConfigError("Configuracao invalida: DOMAIN_GUARD_ALLOWED_EXTENSIONS nao pode ficar vazio")


def initialize_runtime() -> None:
    global _runtime_initialized
    if _runtime_initialized:
        return
    validate_runtime_settings()
    configure_logging()
    init_database()
    _runtime_initialized = True


def save_audit(summary: dict) -> None:
    db_path = Path(CONFIG["AUDIT_DIR"]) / "auditoria.db"
    with closing(sqlite3.connect(db_path)) as conn:
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
        conn.commit()


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in CONFIG["ALLOWED_EXTENSIONS"]


def create_app() -> Flask:
    initialize_runtime()
    flask_app = Flask(__name__)
    flask_app.config["MAX_CONTENT_LENGTH"] = CONFIG["MAX_FILE_SIZE"]
    flask_app.secret_key = CONFIG["SECRET_KEY"] or secrets.token_hex(32)
    flask_app.permanent_session_lifetime = timedelta(hours=CONFIG["SESSION_HOURS"])
    flask_app.config["SESSION_COOKIE_HTTPONLY"] = True
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    flask_app.config["SESSION_COOKIE_SECURE"] = CONFIG["SESSION_COOKIE_SECURE"]
    return flask_app


app = create_app()

PUBLIC_ENDPOINTS = {"login", "static"}


def _login_rate_limit_key(username: str) -> str:
    return username.strip().lower()


def is_login_rate_limited(username: str) -> bool:
    key = _login_rate_limit_key(username)
    if not key:
        return False
    window_seconds = CONFIG["LOGIN_LOCKOUT_MINUTES"] * 60
    now = time.monotonic()
    with _login_attempts_lock:
        attempts = [attempt for attempt in _login_attempts.get(key, []) if now - attempt < window_seconds]
        _login_attempts[key] = attempts
        return len(attempts) >= CONFIG["LOGIN_MAX_ATTEMPTS"]


def register_login_failure(username: str) -> None:
    key = _login_rate_limit_key(username)
    if not key:
        return
    with _login_attempts_lock:
        _login_attempts.setdefault(key, []).append(time.monotonic())


def clear_login_attempts(username: str) -> None:
    key = _login_rate_limit_key(username)
    with _login_attempts_lock:
        _login_attempts.pop(key, None)


def get_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["csrf_token"] = token
    return token


def csrf_token_is_valid() -> bool:
    expected = session.get("csrf_token")
    provided = request.headers.get("X-CSRF-Token", "")
    return bool(expected) and secrets.compare_digest(expected, provided)


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None:
        return None
    if not session.get("authenticated"):
        if request.method == "GET" and request.path == "/":
            return redirect(url_for("login", next=request.path))
        return jsonify({"error": "Sessao expirada. Faca login novamente."}), 401
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not csrf_token_is_valid():
        return jsonify({"error": "Token CSRF invalido ou ausente."}), 403
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if is_login_rate_limited(username):
            error = "Muitas tentativas de login. Aguarde alguns minutos e tente novamente."
            return render_template("login.html", error=error), 429
        password_hash = CONFIG["AUTH_USERS"].get(username)
        if password_hash and check_password_hash(password_hash, password):
            clear_login_attempts(username)
            session.clear()
            session["authenticated"] = True
            session["csrf_token"] = secrets.token_hex(16)
            session.permanent = True
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        register_login_failure(username)
        error = "Usuario ou senha invalidos."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    return render_template(
        "index.html",
        max_file_size_mb=CONFIG["MAX_FILE_SIZE"] // (1024 * 1024),
        csrf_token=get_csrf_token(),
    )


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
        try:
            uploaded.save(target)
        except OSError as exc:
            errors.append(f"Falha ao salvar {uploaded.filename}: {exc}")
            logging.exception("Falha ao salvar upload: %s", uploaded.filename)
            continue
        saved_paths.append(target)
        logging.info("Arquivo recebido: %s", target.name)

    if not saved_paths:
        return jsonify({"error": "Nenhum arquivo valido enviado", "errors": errors}), 400

    try:
        summary = process_files(saved_paths, CONFIG, run_id)
        summary["errors"] = errors + summary["errors"]
        save_audit(summary)
        return jsonify(summary)
    except sqlite3.Error as exc:
        logging.exception("Falha no banco de auditoria")
        return jsonify({"error": f"Falha ao registrar auditoria da execucao: {exc}"}), 500
    except OSError as exc:
        logging.exception("Falha de arquivo durante o processamento")
        return jsonify({"error": f"Falha de acesso a arquivo ou diretorio operacional: {exc}"}), 500
    except Exception as exc:
        logging.exception("Falha inesperada no processamento")
        return jsonify({"error": f"Falha inesperada no processamento: {exc}"}), 500


@app.route("/download/<name>")
def download_file(name: str):
    run_id = request.args.get("run_id")
    try:
        run_paths = get_run_file_paths(CONFIG, run_id) if run_id else {}
        if name == "base_atualizada":
            path = run_updated_base_path(CONFIG, run_id) if run_id else latest_updated_base_path(CONFIG)
        else:
            allowed_downloads = {
                "novos_dominios": run_paths.get("blocklist", CONFIG["OUTPUT_PATH"]),
                "whitelist": run_paths.get("whitelist", CONFIG["WHITELIST_PATH"]),
                "relatorio": run_paths.get("report", CONFIG["REPORT_PATH"]),
            }
            path = allowed_downloads.get(name)
    except ValueError:
        return jsonify({"error": "run_id invalido"}), 400
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
    except TimeoutError as exc:
        logging.warning("Atualizacao de base bloqueada: %s", exc)
        return jsonify({"error": str(exc)}), 409
    except ValueError as exc:
        logging.warning("run_id invalido em confirm-update: %s", exc)
        return jsonify({"error": "run_id invalido"}), 400
    except sqlite3.Error as exc:
        logging.exception("Falha no banco ao confirmar atualizacao")
        return jsonify({"error": f"Falha ao registrar auditoria de rejeicoes: {exc}"}), 500
    except OSError as exc:
        logging.exception("Falha de arquivo ao confirmar atualizacao")
        return jsonify({"error": f"Falha de acesso a arquivo ou diretorio operacional: {exc}"}), 500
    except Exception as exc:
        logging.exception("Falha ao confirmar atualizacao da base")
        return jsonify({"error": f"Falha ao confirmar atualizacao da base: {exc}"}), 500


@app.route("/whitelist")
def view_whitelist():
    run_id = request.args.get("run_id")
    try:
        path = get_run_file_paths(CONFIG, run_id)["whitelist"] if run_id else Path(CONFIG["WHITELIST_PATH"])
    except ValueError:
        return jsonify({"error": "run_id invalido"}), 400
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


if __name__ == "__main__":
    app.run(host=CONFIG["HOST"], port=CONFIG["PORT"], debug=False)
