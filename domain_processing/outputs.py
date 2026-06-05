import json
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .extraction import ensure_directories, load_base_entries, load_domain_file, normalize_block_target
from .models import FileExtraction
from .runtime import acquire_update_lock, get_run_file_paths, read_run_manifest, write_run_manifest


def write_output_files(blocklist: list[str], whitelist: list[dict], report: str, config: dict, run_id: str) -> dict[str, str]:
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    paths = get_run_file_paths(config, run_id)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)

    output_lines = [
        f"# Alvos para Bloqueio - Gerado em {generated_at}",
        f"# Total: {len(blocklist)} alvos",
        f"# Observacao: a lista pode conter dominios completos e URLs especificas",
        "",
        *blocklist,
        "",
    ]
    blocklist_content = "\n".join(output_lines)
    paths["blocklist"].write_text(blocklist_content, encoding="utf-8")
    Path(config["OUTPUT_PATH"]).write_text(blocklist_content, encoding="utf-8")

    whitelist_lines = [
        f"# Whitelist - Dominios Protegidos - {generated_at}",
        f"# Total: {len(whitelist)} dominios",
        "",
    ]
    whitelist_lines.extend(
        f"{item['domain']} (CATEGORIA: {item['category']}; MOTIVO: {item['reason']})" for item in whitelist
    )
    whitelist_lines.append("")
    whitelist_content = "\n".join(whitelist_lines)
    paths["whitelist"].write_text(whitelist_content, encoding="utf-8")
    paths["report"].write_text(report, encoding="utf-8")
    Path(config["WHITELIST_PATH"]).write_text(whitelist_content, encoding="utf-8")
    Path(config["REPORT_PATH"]).write_text(report, encoding="utf-8")
    return {name: str(path) for name, path in paths.items() if name != "run_dir"}


def write_updated_base_file(existing_entries: list[str], new_blocklist: list[str], config: dict) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(config["OUTPUT_DIR"]) / f"base_atualizada_{timestamp}.txt"
    updated = [*existing_entries, *new_blocklist]
    lines = [
        f"# Base atualizada - Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"# Total: {len(updated)} linhas de dominios",
        "",
        *updated,
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def save_pending_update(blocklist: list[str], config: dict, run_id: str) -> dict[str, str]:
    paths = get_run_file_paths(config, run_id)
    payload = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "domains": sorted(set(blocklist)),
    }
    content = json.dumps(payload, ensure_ascii=True, indent=2)
    paths["pending_update"].write_text(content, encoding="utf-8")
    Path(config["PENDING_UPDATE_PATH"]).write_text(content, encoding="utf-8")
    return {"pending_update": str(paths["pending_update"])}


def load_pending_update(config: dict, run_id: str | None = None) -> list[str]:
    path = get_run_file_paths(config, run_id)["pending_update"] if run_id else Path(config["PENDING_UPDATE_PATH"])
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return sorted({target for domain in payload.get("domains", []) if (target := normalize_block_target(domain))})


def normalize_domain_list(domains: list[str] | None) -> list[str]:
    if not domains:
        return []
    return sorted({normalized for domain in domains if (normalized := normalize_block_target(str(domain)))})


def rejected_file_path(config: dict) -> Path:
    configured = config.get("REJECTED_FILE_PATH")
    if configured:
        return Path(configured)
    return Path(config["BASE_FILE_PATH"]).parent / "base_rejeitados.txt"


def save_rejected_domains(config: dict, domains: list[str], run_id: str | None = None) -> int:
    normalized = normalize_domain_list(domains)
    if not normalized:
        return 0

    path = rejected_file_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_domain_file(path)
    merged = sorted(existing.union(normalized))
    path.write_text("\n".join(merged) + "\n", encoding="utf-8")

    audit_dir = config.get("AUDIT_DIR")
    if audit_dir:
        db_path = Path(audit_dir) / "auditoria.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(db_path)) as conn:
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
            rejected_at = datetime.now().isoformat(timespec="seconds")
            conn.executemany(
                """
                INSERT INTO rejected_domains (domain, rejected_at, run_id)
                VALUES (?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    rejected_at = excluded.rejected_at,
                    run_id = excluded.run_id
                """,
                [(domain, rejected_at, run_id) for domain in normalized],
            )
            conn.commit()

    return len(normalized)


def build_report(
    file_results: list[FileExtraction],
    extracted: set[str],
    existing: set[str],
    new_domains: set[str],
    blocklist: list[str],
    whitelist: list[dict],
    existing_discarded: set[str],
    elapsed_seconds: float,
    existing_count: int | None = None,
) -> str:
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    duplicate_total = sum(item.duplicate_count for item in file_results)
    raw_total = sum(item.raw_count or len(item.domains) for item in file_results)
    existing_total = len(existing) if existing_count is None else existing_count
    errors = [f"{item.filename}: {error}" for item in file_results for error in item.errors]

    lines = [
        "RELATORIO DE PROCESSAMENTO DE DOMINIOS E ALVOS",
        f"Gerado em: {generated_at}",
        f"Tempo de processamento: {elapsed_seconds:.2f}s",
        "",
        "ARQUIVOS PROCESSADOS",
    ]
    for item in file_results:
        methods = ", ".join(sorted(set(item.methods)))
        item_total = item.raw_count or len(item.domains)
        lines.append(f"- {item.filename}: {item_total} dominios lidos; {len(item.domains)} unicos; metodos: {methods}")

    lines.extend(
        [
            "",
            "ESTATISTICAS",
            f"Total de dominios lidos: {raw_total}",
            f"Total de dominios extraidos unicos: {len(extracted)}",
            f"Total de dominios existentes na base: {existing_total}",
            f"Total de dominios novos: {len(new_domains)}",
            f"Total de dominios em whitelist: {len(whitelist)}",
            f"Total de dominios para bloqueio: {len(blocklist)}",
            f"Total descartado por ja existir na base: {len(existing_discarded)}",
            f"Duplicatas removidas durante extracao: {duplicate_total}",
            "Obs: a lista de bloqueio pode conter dominios completos e URLs especificas.",
            "",
            "DOMINIOS ENVIADOS PARA WHITELIST",
        ]
    )
    if whitelist:
        for item in whitelist:
            lines.append(f"- {item['domain']} | {item['category']} | {item['reason']}")
    else:
        lines.append("- Nenhum")

    lines.extend(["", "ERROS E AVISOS"])
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- Nenhum")

    lines.extend(
        [
            "",
            "RESUMO JSON",
            json.dumps(
                {
                    "generated_at": generated_at,
                    "files": [item.filename for item in file_results],
                    "read_total": raw_total,
                    "extracted_total": len(extracted),
                    "existing_total": existing_total,
                    "new_total": len(new_domains),
                    "whitelist_total": len(whitelist),
                    "blocklist_total": len(blocklist),
                    "existing_discarded_total": len(existing_discarded),
                    "duplicates_removed": duplicate_total,
                    "errors": errors,
                    "elapsed_seconds": round(elapsed_seconds, 3),
                },
                ensure_ascii=True,
                indent=2,
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def backup_base_file(config: dict) -> Path | None:
    base_path = Path(config["BASE_FILE_PATH"])
    if not base_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(config["BACKUP_DIR"]) / f"base_atual_{timestamp}.txt"
    shutil.copy2(base_path, backup_path)
    return backup_path


def update_base_file(config: dict, new_blocklist: list[str], existing: set[str] | None = None) -> Path | None:
    if not config.get("AUTO_UPDATE_BASE") or not new_blocklist:
        return None
    if config.get("BACKUP_BEFORE_UPDATE"):
        backup_base_file(config)

    base_path = Path(config["BASE_FILE_PATH"])
    current = existing if existing is not None else load_domain_file(base_path)
    updated = sorted(current.union(new_blocklist))
    base_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    return base_path


def confirm_pending_update(
    config: dict,
    run_id: str | None = None,
    approved_domains: list[str] | None = None,
    rejected_domains: list[str] | None = None,
) -> dict:
    ensure_directories(config)
    with acquire_update_lock(config):
        pending = load_pending_update(config, run_id)
        pending_set = set(pending)
        approved = normalize_domain_list(approved_domains)
        rejected = sorted(set(normalize_domain_list(rejected_domains)).intersection(pending_set))
        selected = sorted(set(approved).intersection(pending_set)) if approved_domains is not None else pending
        rejected_count = save_rejected_domains(config, rejected, run_id)
        base_path = Path(config["BASE_FILE_PATH"])
        current = load_domain_file(base_path)
        existing_entries = load_base_entries(base_path)
        domains_to_add = sorted(set(selected) - current)

        if not domains_to_add:
            latest = run_updated_base_path(config, run_id) if run_id else latest_updated_base_path(config)
            return {
                "run_id": run_id,
                "added_count": 0,
                "rejected_count": rejected_count,
                "ignored_existing_count": len(set(selected).intersection(current)),
                "updated_base_file": latest.name if latest else None,
                "base_total": len(existing_entries),
            }

        if config.get("BACKUP_BEFORE_UPDATE"):
            backup_base_file(config)

        updated_base_path = write_updated_base_file(existing_entries, domains_to_add, config)
        updated = [*existing_entries, *domains_to_add]
        base_path.write_text("\n".join(updated) + "\n", encoding="utf-8")

        if run_id:
            manifest = read_run_manifest(config, run_id) or {"run_id": run_id}
            manifest["base_update"] = {
                "confirmed_at": datetime.now().isoformat(timespec="seconds"),
                "added_count": len(domains_to_add),
                "rejected_count": rejected_count,
                "updated_base_file": updated_base_path.name,
            }
            write_run_manifest(config, run_id, manifest)

        return {
            "run_id": run_id,
            "added_count": len(domains_to_add),
            "rejected_count": rejected_count,
            "ignored_existing_count": len(set(selected).intersection(current)),
            "updated_base_file": updated_base_path.name,
            "base_total": len(updated),
        }


def run_updated_base_path(config: dict, run_id: str | None) -> Path | None:
    if not run_id:
        return None

    manifest = read_run_manifest(config, run_id) or {}
    base_update = manifest.get("base_update") or {}
    filename = base_update.get("updated_base_file")
    if not filename:
        return None

    path = Path(config["OUTPUT_DIR"]) / filename
    return path if path.exists() else None


def latest_updated_base_path(config: dict) -> Path | None:
    files = sorted(Path(config["OUTPUT_DIR"]).glob("base_atualizada_*.txt"), key=lambda item: item.stat().st_mtime)
    return files[-1] if files else None
