import re
from pathlib import Path
from typing import Iterable

from .models import FileExtraction


DOMAIN_PATTERNS = [
    re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"),
]

NOISE_DOMAINS = {
    "t.com",
}


def ensure_directories(config: dict) -> None:
    for key in ("UPLOAD_DIR", "OUTPUT_DIR", "RUNS_DIR", "AUDIT_DIR", "BACKUP_DIR", "LOG_DIR"):
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
