import json
import logging
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


DOMAIN_PATTERNS = [
    re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"),
    re.compile(r"(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}"),
]

NOISE_DOMAINS = {
    "t.com",
}

WHITELIST_PATTERNS = {
    "BANCOS": [
        "bancobrasil.com.br",
        "bcb.gov.br",
        "bb.com.br",
        "caixa.com.br",
        "itau.com.br",
        "bradesco.com.br",
        "santander.com.br",
        "caixa.gov.br",
        "nubank.com.br",
        "inter.co",
        "bancointer.com.br",
        "c6bank.com.br",
        "banrisul.com.br",
        "sicredi.com.br",
        "sicoob.com.br",
        "btgpactual.com",
    ],
    "REDES_SOCIAIS": [
        "facebook.com",
        "fb.com",
        "instagram.com",
        "t.co",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "youtube.com",
        "google.com",
        "tiktok.com",
        "whatsapp.com",
        "telegram.org",
    ],
    "GOVERNO": [
        "gov",
        "gov.br",
        "jus.br",
        "mp.br",
        "leg.br",
        "def.br",
        "anatel.gov.br",
        "anatel.br",
        "receita.fazenda.gov.br",
        "inss.gov.br",
        "detran.*.gov.br",
        "policia*.gov.br",
        "justica.gov.br",
        "stf.jus.br",
        "tse.jus.br",
        "tre-*.jus.br",
    ],
    "ORGAOS_PUBLICOS": [
        "ibge.gov.br",
        "inep.gov.br",
        "anvisa.gov.br",
        "bacen.gov.br",
        "bcb.gov.br",
        "cvm.gov.br",
        "ans.gov.br",
    ],
    "SEGURANCA": [
        "mil.br",
        "pf.gov.br",
        "prf.gov.br",
        "abin.gov.br",
        "exercito.mil.br",
        "marinha.mil.br",
        "fab.mil.br",
    ],
    "EDUCACAO": [
        "edu.br",
        "mec.gov.br",
        "capes.gov.br",
        "usp.br",
        "unicamp.br",
        "ufrj.br",
        "ufmg.br",
        "unesp.br",
    ],
    "SAUDE": [
        "saude.gov.br",
        "fiocruz.br",
        "butantan.gov.br",
        "hospitais*.gov.br",
        "ans.gov.br",
    ],
}

BORDERLINE_KEYWORDS = {
    "banco": "POSSIVEL_BANCO",
    "bank": "POSSIVEL_BANCO",
    "gov": "POSSIVEL_GOVERNO",
    "prefeitura": "POSSIVEL_ORGAO_PUBLICO",
    "camara": "POSSIVEL_ORGAO_PUBLICO",
    "policia": "POSSIVEL_SEGURANCA",
    "saude": "POSSIVEL_SAUDE",
    "hospital": "POSSIVEL_SAUDE",
    "universidade": "POSSIVEL_EDUCACAO",
    "faculdade": "POSSIVEL_EDUCACAO",
    "tribunal": "POSSIVEL_JUSTICA",
}


@dataclass
class FileExtraction:
    filename: str
    domains: set[str] = field(default_factory=set)
    duplicate_count: int = 0
    raw_count: int = 0
    errors: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


def ensure_directories(config: dict) -> None:
    for key in ("UPLOAD_DIR", "OUTPUT_DIR", "AUDIT_DIR", "BACKUP_DIR", "LOG_DIR"):
        Path(config[key]).mkdir(parents=True, exist_ok=True)
    Path(config["BASE_FILE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    Path(config["BASE_FILE_PATH"]).touch(exist_ok=True)


def normalize_domain(value: str) -> str | None:
    candidate = value.strip().lower()
    candidate = re.sub(r"^[a-z][a-z0-9+.-]*://", "", candidate)
    candidate = candidate.split("/")[0].split("?")[0].split("#")[0]
    candidate = candidate.split("@")[-1]
    candidate = candidate.strip(" \t\r\n'\"`()[]{}<>.,;:|\\")
    candidate = candidate.removeprefix("*.")
    candidate = candidate.removeprefix("www.")
    candidate = re.sub(r":\d+$", "", candidate)

    if not candidate or "." not in candidate or len(candidate) > 253:
        return None

    labels = candidate.split(".")
    if len(labels[-1]) < 2 or not labels[-1].isalpha():
        return None

    for label in labels:
        if not label or len(label) > 63:
            return None
        if label.startswith("-") or label.endswith("-"):
            return None
        if not re.fullmatch(r"[a-z0-9-]+", label):
            return None

    if candidate in NOISE_DOMAINS:
        return None

    return candidate


def merge_wrapped_domain_lines(lines: Iterable[str]) -> list[str]:
    merged: list[str] = []
    items = list(lines)
    index = 0

    while index < len(items):
        current = items[index].strip()
        next_value = items[index + 1].strip() if index + 1 < len(items) else ""

        if current.endswith("-") and next_value:
            joined = f"{current[:-1]}{next_value}"
            if normalize_domain(joined):
                merged.append(joined)
                index += 2
                continue

        merged.append(current)
        index += 1

    return merged


def extract_domains_from_text(text: str) -> tuple[set[str], int]:
    normalized: list[str] = []
    for pattern in DOMAIN_PATTERNS:
        for match in pattern.finditer(text or ""):
            if match.start() > 0 and text[match.start() - 1] == "@":
                continue
            domain = normalize_domain(match.group(0))
            if domain:
                normalized.append(domain)

    unique = set(normalized)
    return unique, max(0, len(normalized) - len(unique))


def extract_domains_from_lines(lines: Iterable[str]) -> tuple[set[str], int, int]:
    normalized: list[str] = []
    safe_line = re.compile(r"^[a-zA-Z0-9*._:/?#@%+\-]+$")

    for line in lines:
        value = line.strip()
        if "@" in value:
            continue
        if not value or not safe_line.fullmatch(value):
            continue
        domain = normalize_domain(value)
        if domain:
            normalized.append(domain)

    unique = set(normalized)
    return unique, max(0, len(normalized) - len(unique)), len(normalized)


def extract_txt(path: Path) -> FileExtraction:
    result = FileExtraction(filename=path.name, methods=["txt"])
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        result.domains, result.duplicate_count = extract_domains_from_text(text)
        result.raw_count = len(result.domains) + result.duplicate_count
    except OSError as exc:
        result.errors.append(f"Falha ao ler TXT: {exc}")
    return result


def extract_pdf(
    path: Path,
    enable_ocr: bool,
    ocr_language: str,
    ocr_only_if_no_domains: bool = True,
) -> FileExtraction:
    result = FileExtraction(filename=path.name)
    text_parts: list[str] = []

    try:
        import fitz

        with fitz.open(path) as doc:
            lines: list[str] = []
            for page in doc:
                lines.extend(page.get_text("text").splitlines())

        lines = merge_wrapped_domain_lines(lines)
        result.domains, result.duplicate_count, result.raw_count = extract_domains_from_lines(lines)
        if result.domains:
            result.methods.append("pymupdf-lines")
            if enable_ocr and ocr_only_if_no_domains:
                result.errors.append("OCR ignorado: dominios encontrados na extracao por linha")
            return result

        text_parts.append("\n".join(lines))
        result.methods.append("pymupdf-text-fallback")
    except ImportError:
        result.errors.append("PyMuPDF nao instalado; fallback para pdfplumber")
    except Exception as exc:
        result.errors.append(f"Falha na extracao rapida do PDF: {exc}")

    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    result.methods.append("pdfplumber-text")
                    text_parts.append(page_text)

                try:
                    tables = page.extract_tables() or []
                    for table in tables:
                        for row in table:
                            text_parts.append(" ".join(cell or "" for cell in row))
                    if tables:
                        result.methods.append("pdfplumber-table")
                except Exception as exc:  # pragma: no cover - depends on PDF internals
                    result.errors.append(f"Aviso ao extrair tabela: {exc}")
    except ImportError:
        result.errors.append("pdfplumber nao instalado; extracao de texto estruturado indisponivel")
    except Exception as exc:
        result.errors.append(f"Falha na extracao estruturada do PDF: {exc}")

    structured_domains, structured_duplicates = extract_domains_from_text("\n".join(text_parts))
    should_run_ocr = enable_ocr and (not ocr_only_if_no_domains or not structured_domains)

    if should_run_ocr:
        ocr_text, ocr_errors = extract_pdf_ocr(path, ocr_language)
        if ocr_text:
            result.methods.append("ocr")
            text_parts.append(ocr_text)
        result.errors.extend(ocr_errors)
    elif enable_ocr and ocr_only_if_no_domains and structured_domains:
        result.errors.append("OCR ignorado: dominios encontrados na extracao estruturada")

    result.domains, result.duplicate_count = extract_domains_from_text("\n".join(text_parts))
    result.raw_count = len(result.domains) + result.duplicate_count
    if structured_domains and not should_run_ocr:
        result.duplicate_count = structured_duplicates
        result.raw_count = len(result.domains) + result.duplicate_count
    if not result.methods:
        result.methods.append("pdf-sem-texto")
    return result


def extract_pdf_ocr(path: Path, ocr_language: str) -> tuple[str, list[str]]:
    errors: list[str] = []
    text_parts: list[str] = []
    try:
        import fitz
        import pytesseract
        from PIL import Image
    except Exception as exc:
        return "", [f"OCR indisponivel; falha ao carregar dependencias: {exc}"]

    try:
        with fitz.open(path) as doc:
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text_parts.append(pytesseract.image_to_string(image, lang=ocr_language))
    except Exception as exc:  # pragma: no cover - requires local OCR binary
        errors.append(f"Falha no OCR: {exc}")
    return "\n".join(text_parts), errors


def extract_file(path: Path, config: dict) -> FileExtraction:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return extract_txt(path)
    if suffix == ".pdf":
        return extract_pdf(
            path,
            config["ENABLE_OCR"],
            config["OCR_LANGUAGE"],
            config.get("OCR_ONLY_IF_NO_DOMAINS", True),
        )
    return FileExtraction(filename=path.name, errors=["Tipo de arquivo nao permitido"])


def load_domain_file(path: Path) -> set[str]:
    if not path.exists():
        return set()
    domains: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        clean = clean.split()[0]
        domain = normalize_domain(clean)
        if domain:
            domains.add(domain)
    return domains


def load_base_entries(path: Path) -> list[str]:
    if not path.exists():
        return []
    entries: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        clean = line.strip()
        if clean and not clean.startswith("#"):
            entries.append(clean)
    return entries


def wildcard_to_regex(pattern: str) -> re.Pattern[str]:
    escaped = re.escape(pattern.lower()).replace(r"\*", r"[a-z0-9-]*")
    return re.compile(rf"(^|\.){escaped}$")


def classify_sensitive(domain: str) -> tuple[bool, str | None, str | None]:
    for category, patterns in WHITELIST_PATTERNS.items():
        for pattern in patterns:
            normalized_pattern = pattern.lower()
            if "*" in normalized_pattern:
                if wildcard_to_regex(normalized_pattern).search(domain):
                    return True, category, f"padrao wildcard: {pattern}"
                continue

            if domain == normalized_pattern or domain.endswith(f".{normalized_pattern}"):
                return True, category, f"padrao protegido: {pattern}"

    for keyword, category in BORDERLINE_KEYWORDS.items():
        if keyword == "gov" and keyword not in domain.split("."):
            continue
        if keyword in domain:
            return True, category, f"keyword borderline: {keyword}"

    return False, None, None


def compare_new_domains(extracted: Iterable[str], existing: Iterable[str]) -> set[str]:
    return set(extracted) - set(existing)


def split_whitelist(domains: Iterable[str]) -> tuple[list[str], list[dict]]:
    blocklist: list[str] = []
    whitelist: list[dict] = []
    for domain in sorted(domains):
        sensitive, category, reason = classify_sensitive(domain)
        if sensitive:
            whitelist.append({"domain": domain, "category": category, "reason": reason})
        else:
            blocklist.append(domain)
    return blocklist, whitelist


def classify_for_base_update(extracted: Iterable[str], existing: Iterable[str]) -> tuple[list[str], list[dict], set[str]]:
    candidates, whitelist = split_whitelist(extracted)
    existing_set = set(existing)
    existing_discarded = set(candidates).intersection(existing_set)
    blocklist = sorted(set(candidates) - existing_set)
    return blocklist, whitelist, existing_discarded


def write_output_files(blocklist: list[str], whitelist: list[dict], report: str, config: dict) -> None:
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    output_lines = [
        f"# Dominios para Bloqueio - Gerado em {generated_at}",
        f"# Total: {len(blocklist)} dominios",
        "",
        *blocklist,
        "",
    ]
    Path(config["OUTPUT_PATH"]).write_text("\n".join(output_lines), encoding="utf-8")

    whitelist_lines = [
        f"# Whitelist - Dominios Protegidos - {generated_at}",
        f"# Total: {len(whitelist)} dominios",
        "",
    ]
    whitelist_lines.extend(
        f"{item['domain']} (CATEGORIA: {item['category']}; MOTIVO: {item['reason']})" for item in whitelist
    )
    whitelist_lines.append("")
    Path(config["WHITELIST_PATH"]).write_text("\n".join(whitelist_lines), encoding="utf-8")
    Path(config["REPORT_PATH"]).write_text(report, encoding="utf-8")


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


def save_pending_update(blocklist: list[str], config: dict) -> None:
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "domains": sorted(set(blocklist)),
    }
    Path(config["PENDING_UPDATE_PATH"]).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def load_pending_update(config: dict) -> list[str]:
    path = Path(config["PENDING_UPDATE_PATH"])
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return sorted({domain for domain in payload.get("domains", []) if normalize_domain(domain)})


def build_report(
    file_results: list[FileExtraction],
    extracted: set[str],
    existing: set[str],
    new_domains: set[str],
    blocklist: list[str],
    whitelist: list[dict],
    existing_discarded: set[str],
    elapsed_seconds: float,
) -> str:
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    duplicate_total = sum(item.duplicate_count for item in file_results)
    raw_total = sum(item.raw_count or len(item.domains) for item in file_results)
    errors = [f"{item.filename}: {error}" for item in file_results for error in item.errors]

    lines = [
        "RELATORIO DE PROCESSAMENTO DE DOMINIOS",
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
            f"Total de dominios existentes na base: {len(existing)}",
            f"Total de dominios novos: {len(new_domains)}",
            f"Total de dominios em whitelist: {len(whitelist)}",
            f"Total de dominios para bloqueio: {len(blocklist)}",
            f"Total descartado por ja existir na base: {len(existing_discarded)}",
            f"Duplicatas removidas durante extracao: {duplicate_total}",
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
                    "existing_total": len(existing),
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


def confirm_pending_update(config: dict) -> dict:
    ensure_directories(config)
    pending = load_pending_update(config)
    base_path = Path(config["BASE_FILE_PATH"])
    current = load_domain_file(base_path)
    existing_entries = load_base_entries(base_path)
    domains_to_add = sorted(set(pending) - current)

    if not domains_to_add:
        latest = latest_updated_base_path(config)
        return {
            "added_count": 0,
            "ignored_existing_count": len(set(pending).intersection(current)),
            "updated_base_file": latest.name if latest else None,
            "base_total": len(existing_entries),
        }

    if config.get("BACKUP_BEFORE_UPDATE"):
        backup_base_file(config)

    updated_base_path = write_updated_base_file(existing_entries, domains_to_add, config)
    updated = [*existing_entries, *domains_to_add]
    base_path.write_text("\n".join(updated) + "\n", encoding="utf-8")

    return {
        "added_count": len(domains_to_add),
        "ignored_existing_count": len(set(pending).intersection(current)),
        "updated_base_file": updated_base_path.name,
        "base_total": len(updated),
    }


def latest_updated_base_path(config: dict) -> Path | None:
    files = sorted(Path(config["OUTPUT_DIR"]).glob("base_atualizada_*.txt"), key=lambda item: item.stat().st_mtime)
    return files[-1] if files else None


def process_files(paths: list[Path], config: dict) -> dict:
    start = time.perf_counter()
    ensure_directories(config)

    file_results = [extract_file(path, config) for path in paths]
    extracted = set().union(*(item.domains for item in file_results)) if file_results else set()
    existing = load_domain_file(Path(config["BASE_FILE_PATH"]))
    blocklist, whitelist, existing_discarded = classify_for_base_update(extracted, existing)
    new_domains = set(blocklist)
    elapsed = time.perf_counter() - start
    report = build_report(file_results, extracted, existing, new_domains, blocklist, whitelist, existing_discarded, elapsed)

    write_output_files(blocklist, whitelist, report, config)
    save_pending_update(blocklist, config)

    summary = {
        "files_processed": [item.filename for item in file_results],
        "domains_extracted": sum(item.raw_count or len(item.domains) for item in file_results),
        "domains_unique": len(extracted),
        "existing_domains": len(existing),
        "new_domains": len(new_domains),
        "whitelist_count": len(whitelist),
        "blocklist_count": len(blocklist),
        "existing_discarded_count": len(existing_discarded),
        "duplicates_removed": sum(item.duplicate_count for item in file_results),
        "errors": [f"{item.filename}: {error}" for item in file_results for error in item.errors],
        "elapsed_seconds": round(elapsed, 3),
        "pending_update_available": bool(blocklist),
        "blocklist": blocklist,
        "whitelist": whitelist,
        "preview_blocklist": blocklist[:25],
        "preview_whitelist": whitelist[:25],
    }
    logging.info("Processamento concluido: %s", summary)
    return summary
