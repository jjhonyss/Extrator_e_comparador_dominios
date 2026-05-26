import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .classification import classify_for_base_update
from .extraction import ensure_directories, extract_file, load_domain_file
from .outputs import build_report, save_pending_update, write_output_files
from .runtime import write_run_manifest


def process_files(paths: list[Path], config: dict, run_id: str) -> dict:
    start = time.perf_counter()
    ensure_directories(config)

    max_workers = min(len(paths), max(1, (os.cpu_count() or 1))) if paths else 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        file_results = list(executor.map(lambda path: extract_file(path, config), paths))

    extracted = set().union(*(item.domains for item in file_results)) if file_results else set()
    existing = load_domain_file(Path(config["BASE_FILE_PATH"]))
    blocklist, whitelist, existing_discarded = classify_for_base_update(extracted, existing)
    new_domains = set(blocklist)
    elapsed = time.perf_counter() - start
    report = build_report(file_results, extracted, existing, new_domains, blocklist, whitelist, existing_discarded, elapsed)

    artifact_paths = write_output_files(blocklist, whitelist, report, config, run_id)
    pending_paths = save_pending_update(blocklist, config, run_id)

    summary = {
        "run_id": run_id,
        "files_processed": [item.filename for item in file_results],
        "file_results": [
            {
                "filename": item.filename,
                "domains_unique": len(item.domains),
                "domains_read": item.raw_count or len(item.domains),
                "duplicate_count": item.duplicate_count,
                "methods": sorted(set(item.methods)),
                "errors": item.errors,
            }
            for item in file_results
        ],
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
        "artifacts": artifact_paths | pending_paths,
    }
    write_run_manifest(
        config,
        run_id,
        {
            "run_id": run_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "files_processed": summary["files_processed"],
            "artifact_paths": summary["artifacts"],
            "pending_update_available": summary["pending_update_available"],
        },
    )
    logging.info("Processamento concluido: %s", summary)
    return summary
