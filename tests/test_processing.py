import tempfile
import unittest
import sqlite3
from contextlib import closing
from pathlib import Path

from processing import (
    apply_target_corrections,
    block_target_domain,
    build_report,
    classify_sensitive,
    compare_new_domains,
    classify_for_base_update,
    confirm_pending_update,
    extract_domains_from_lines,
    extract_domains_from_pdf_text,
    extract_domains_from_text,
    is_specific_block_target,
    load_base_entries,
    load_base_reference_state,
    load_base_reference_domains,
    load_domain_file,
    load_target_corrections,
    normalize_block_target,
    read_run_manifest,
    generate_run_id,
    get_run_file_paths,
    run_updated_base_path,
    extract_txt,
    merge_wrapped_domain_lines,
    normalize_base_domain,
    normalize_domain,
    process_files,
    split_whitelist,
)


class ProcessingTests(unittest.TestCase):
    def test_normalize_domain(self):
        self.assertEqual(normalize_domain("https://www.Example.COM/path"), "example.com")
        self.assertEqual(normalize_domain("*.Gov.BR"), "gov.br")
        self.assertEqual(normalize_domain("www.bet.com"), "bet.com")
        self.assertIsNone(normalize_domain("www.bet"))
        self.assertEqual(normalize_domain("www-site.com"), "www-site.com")
        self.assertIsNone(normalize_domain("invalid_domain"))
        self.assertIsNone(normalize_domain("example.123"))
        self.assertIsNone(normalize_domain("t.com"))
        self.assertIsNone(normalize_domain("to.com"))

    def test_normalize_block_target_preserves_specific_url_path(self):
        self.assertEqual(normalize_block_target("https://Erome.com/a/2qHOEUJi"), "erome.com/a/2qHOEUJi")
        self.assertEqual(normalize_block_target("erome.com/lobato?tt=posts"), "erome.com/lobato?tt=posts")
        self.assertEqual(block_target_domain("erome.com/a/2qHOEUJi"), "erome.com")
        self.assertTrue(is_specific_block_target("erome.com/a/2qHOEUJi"))

    def test_load_target_corrections_reads_manual_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "correcoes.txt"
            path.write_text("0705x.bet => 05x.bet\n", encoding="utf-8")
            corrections = load_target_corrections({"TARGET_CORRECTIONS_PATH": path})

        self.assertEqual(corrections, {"0705x.bet": "05x.bet"})

    def test_apply_target_corrections_rewrites_only_listed_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "correcoes.txt"
            path.write_text("0705x.bet => 05x.bet\n", encoding="utf-8")
            corrected = apply_target_corrections(
                {"0705x.bet", "07bet.com"},
                {"TARGET_CORRECTIONS_PATH": path},
            )

        self.assertEqual(corrected, {"05x.bet", "07bet.com"})

    def test_normalize_base_domain_is_strict_with_malformed_entries(self):
        self.assertEqual(normalize_base_domain("example.com"), "example.com")
        self.assertEqual(normalize_base_domain("www.example.com"), "example.com")
        self.assertEqual(normalize_base_domain("www-site.com"), "www-site.com")
        self.assertIsNone(normalize_base_domain("example.com:2087"))
        self.assertIsNone(normalize_base_domain("example.com/path"))
        self.assertIsNone(normalize_base_domain("example.com."))

    def test_load_base_reference_domains_keeps_authoritative_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "base.txt"
            path.write_text("pc.537k7.com:8888\nbetl 8k.app\n", encoding="utf-8")

            domains, entry_count = load_base_reference_domains(path)

        self.assertEqual(entry_count, 2)
        self.assertIn("pc.537k7.com", domains)
        self.assertIn("8k.app", domains)

    def test_load_base_reference_state_keeps_specific_paths_without_promoting_domain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "base.txt"
            path.write_text("erome.com/a/2qHOEUJi\n", encoding="utf-8")

            exact_targets, comparable_domains, entry_count = load_base_reference_state(path)

        self.assertEqual(entry_count, 1)
        self.assertEqual(exact_targets, {"erome.com/a/2qHOEUJi"})
        self.assertEqual(comparable_domains, set())

    def test_extract_domains_from_text_deduplicates(self):
        text = "Bloquear bet365.com e bet365.com. Preservar anatel.gov.br"
        domains, duplicates = extract_domains_from_text(text)
        self.assertIn("bet365.com", domains)
        self.assertIn("anatel.gov.br", domains)
        self.assertEqual(duplicates, 1)

    def test_extract_domains_from_text_does_not_double_count_single_match(self):
        domains, duplicates = extract_domains_from_text("bet365.com")
        self.assertEqual(domains, {"bet365.com"})
        self.assertEqual(duplicates, 0)

    def test_extract_domains_from_text_ignores_pipe_fragmented_line(self):
        domains, duplicates = extract_domains_from_text("unitv | macro-tv-online-recarga.webnod | e.page")
        self.assertEqual(domains, set())
        self.assertEqual(duplicates, 0)

    def test_extract_domains_from_pdf_text_treats_pipe_as_visual_noise(self):
        domains, duplicates = extract_domains_from_pdf_text("unitv | macro-tv-online-recarga.webnod | e.page")
        self.assertEqual(domains, {"macro-tv-online-recarga.webnode.page"})
        self.assertEqual(duplicates, 0)

    def test_extract_domains_from_pdf_text_extracts_multiple_candidates(self):
        domains, duplicates = extract_domains_from_pdf_text("portal | alpha.com | beta.net")
        self.assertEqual(domains, {"alpha.com", "beta.net"})
        self.assertEqual(duplicates, 0)

    def test_extract_domains_from_text_ignores_email_domains(self):
        domains, _duplicates = extract_domains_from_text("Contato: suporte@adapta.org.br bloquear alvo.bet")
        self.assertNotIn("adapta.org.br", domains)
        self.assertIn("alvo.bet", domains)

    def test_extract_domains_from_lines_counts_exact_domain_rows(self):
        domains, duplicates, raw_count = extract_domains_from_lines([
            "bet365.com",
            "bet365.com",
            "suporte@adapta.org.br",
            "Novo Bloqueio / New Blockage",
            "20/05/2026",
        ])
        self.assertEqual(domains, {"bet365.com"})
        self.assertEqual(duplicates, 1)
        self.assertEqual(raw_count, 2)

    def test_extract_domains_from_lines_preserves_specific_url_targets(self):
        domains, duplicates, raw_count = extract_domains_from_lines([
            "erome.com/a/2qHOEUJi",
            "erome.com/lobato?tt=posts",
            "erome.com/a/2qHOEUJi",
        ])
        self.assertEqual(domains, {"erome.com/a/2qHOEUJi", "erome.com/lobato?tt=posts"})
        self.assertEqual(duplicates, 1)
        self.assertEqual(raw_count, 3)

    def test_merge_wrapped_domain_lines_rebuilds_split_punycode(self):
        lines = merge_wrapped_domain_lines(["xn--kksrenoveringlinkping-", "hecq.nu", "t.com"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("xn--kksrenoveringlinkpinghecq.nu", domains)
        self.assertNotIn("hecq.nu", domains)
        self.assertNotIn("t.com", domains)

    def test_merge_wrapped_domain_lines_rebuilds_pdf_line_break_domain(self):
        lines = merge_wrapped_domain_lines(["tv-0800-tv-online-ao-vivo.softoni", "c.com.br", "tv0800.click"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("tv-0800-tv-online-ao-vivo.softonic.com.br", domains)
        self.assertIn("tv0800.click", domains)
        self.assertNotIn("c.com.br", domains)

    def test_merge_wrapped_domain_lines_rebuilds_softonic_break_domain(self):
        lines = merge_wrapped_domain_lines(["megacine-os-melhores-filmes.so", "ftonic.com.br", "alpha.com"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("megacine-os-melhores-filmes.softonic.com.br", domains)
        self.assertIn("alpha.com", domains)
        self.assertNotIn("ftonic.com.br", domains)

    def test_merge_wrapped_domain_lines_rebuilds_single_label_tld_break(self):
        lines = merge_wrapped_domain_lines(["codigoserecargasoficial.catalog.k", "yte.site", "alpha.com"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("codigoserecargasoficial.catalog.kyte.site", domains)
        self.assertIn("alpha.com", domains)
        self.assertNotIn("yte.site", domains)

    def test_merge_wrapped_domain_lines_does_not_join_adjacent_valid_domains(self):
        lines = merge_wrapped_domain_lines(["abinteligencia.com.br", "rgacom.com.br", "academiarecargas.com", "rossnet.com.br"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("abinteligencia.com.br", domains)
        self.assertIn("rgacom.com.br", domains)
        self.assertIn("academiarecargas.com", domains)
        self.assertIn("rossnet.com.br", domains)
        self.assertNotIn("abinteligencia.com.brrgacom.com.br", domains)
        self.assertNotIn("academiarecargas.comrossnet.com.br", domains)

    def test_merge_wrapped_domain_lines_keeps_real_hyphen_when_joining_pdf_break(self):
        lines = merge_wrapped_domain_lines(["storage-usa-sv07-", "user78787451.6siusan.workers.dev", "alpha.com"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("storage-usa-sv07-user78787451.6siusan.workers.dev", domains)
        self.assertIn("alpha.com", domains)
        self.assertNotIn("storage-usa-sv07user78787451.6siusan.workers.dev", domains)

    def test_merge_wrapped_domain_lines_does_not_join_adjacent_valid_domains(self):
        lines = merge_wrapped_domain_lines(["abinteligencia.com.br", "rgacom.com.br", "academiarecargas.com", "rossnet.com.br"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("abinteligencia.com.br", domains)
        self.assertIn("rgacom.com.br", domains)
        self.assertIn("academiarecargas.com", domains)
        self.assertIn("rossnet.com.br", domains)
        self.assertNotIn("abinteligencia.com.brrgacom.com.br", domains)
        self.assertNotIn("academiarecargas.comrossnet.com.br", domains)

    def test_merge_wrapped_domain_lines_rebuilds_pdf_pipe_style_fragment(self):
        lines = merge_wrapped_domain_lines(["macro-tv-online-recarga.webnod", "e.page", "alpha.com"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("macro-tv-online-recarga.webnode.page", domains)
        self.assertIn("alpha.com", domains)
        self.assertNotIn("e.page", domains)

    def test_merge_wrapped_domain_lines_does_not_join_valid_domain_with_short_country_tld(self):
        # Regressao: xilften.fr + www.xilften.fr nao deve virar xilften.frwww.xilften.fr
        lines = merge_wrapped_domain_lines(["xilften.fr", "www.xilften.fr", "alpha.com"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("xilften.fr", domains)
        self.assertIn("alpha.com", domains)
        self.assertNotIn("xilften.frwww.xilften.fr", domains)

    def test_merge_wrapped_domain_lines_does_not_join_valid_domain_followed_by_uncommon_tld(self):
        # Regressao: overflix.ac + www.overflixtv.cyou nao deve virar overflix.acwww.overflixtv.cyou
        lines = merge_wrapped_domain_lines(["overflix.ac", "www.overflixtv.cyou", "alpha.com"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("overflix.ac", domains)
        self.assertIn("overflixtv.cyou", domains)
        self.assertIn("alpha.com", domains)
        self.assertNotIn("overflix.acwww.overflixtv.cyou", domains)

    def test_merge_wrapped_domain_lines_does_not_join_multi_label_br_with_uncommon_tld(self):
        # Regressao: dunatv.pro.br + duosat.live e reieletrotv.com.br + unitv.bet nao devem se fundir
        lines = merge_wrapped_domain_lines(["dunatv.pro.br", "duosat.live", "reieletrotv.com.br", "unitv.bet"])
        domains, _duplicates, _raw_count = extract_domains_from_lines(lines)
        self.assertIn("dunatv.pro.br", domains)
        self.assertIn("duosat.live", domains)
        self.assertIn("reieletrotv.com.br", domains)
        self.assertIn("unitv.bet", domains)
        self.assertNotIn("dunatv.pro.brduosat.live", domains)
        self.assertNotIn("reieletrotv.com.brunitv.bet", domains)


    def test_extract_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "entrada.txt"
            path.write_text("casino-online.net\ninstagram.com\n", encoding="utf-8")
            result = extract_txt(path)
        self.assertEqual(result.domains, {"casino-online.net", "instagram.com"})
        self.assertFalse(result.errors)

    def test_extract_txt_applies_manual_corrections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "entrada.txt"
            corrections = root / "correcoes.txt"
            path.write_text("0705x.bet\n07bet.com\n", encoding="utf-8")
            corrections.write_text("0705x.bet => 05x.bet\n", encoding="utf-8")
            result = extract_txt(path, {"TARGET_CORRECTIONS_PATH": corrections})

        self.assertEqual(result.domains, {"05x.bet", "07bet.com"})

    def test_extract_txt_counts_input_lines_without_partial_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "entrada.txt"
            path.write_text("betl 8k.app\npc.salto-alto777bet\nvalidobet.bet\n", encoding="utf-8")
            result = extract_txt(path)

        self.assertEqual(result.raw_count, 3)
        self.assertEqual(result.domains, {"validobet.bet"})

    def test_compare_new_domains(self):
        extracted = {"a.com", "b.com", "c.com"}
        existing = {"a.com", "c.com"}
        self.assertEqual(compare_new_domains(extracted, existing), {"b.com"})

    def test_classify_sensitive(self):
        self.assertEqual(classify_sensitive("anatel.gov.br")[1], "GOVERNO")
        self.assertEqual(classify_sensitive("tribunal.jus.br")[1], "GOVERNO")
        self.assertEqual(classify_sensitive("facebook.com")[1], "REDES_SOCIAIS")
        self.assertEqual(classify_sensitive("t.co")[1], "REDES_SOCIAIS")
        self.assertEqual(classify_sensitive("bcb.gov.br")[1], "BANCOS")
        self.assertEqual(classify_sensitive("abta.org.br")[1], "ORGAOS_PUBLICOS")
        self.assertEqual(classify_sensitive("sub.instagram.com")[1], "REDES_SOCIAIS")
        self.assertEqual(classify_sensitive("bet365.com"), (False, None, None))
        self.assertEqual(classify_sensitive("jogovip.bet"), (False, None, None))
        self.assertEqual(classify_sensitive("bankroll-bet.com"), (False, None, None))
        self.assertEqual(classify_sensitive("meu-banco.com"), (False, None, None))
        self.assertEqual(classify_sensitive("777bankgame.com"), (False, None, None))
        self.assertEqual(classify_sensitive("ds.bancodobrasil777bet.com"), (False, None, None))
        self.assertEqual(classify_sensitive("faculdadescoc.com.br"), (False, None, None))

    def test_split_whitelist(self):
        blocklist, whitelist = split_whitelist({"bet365.com", "bancobrasil.com.br"})
        self.assertEqual(blocklist, ["bet365.com"])
        self.assertEqual(whitelist[0]["category"], "BANCOS")

    def test_split_whitelist_blocks_domains_with_misleading_keywords(self):
        blocklist, whitelist = split_whitelist({
            "777bankgame.com",
            "ds.bancodobrasil777bet.com",
            "faculdadescoc.com.br",
        })
        self.assertEqual(
            blocklist,
            ["777bankgame.com", "ds.bancodobrasil777bet.com", "faculdadescoc.com.br"],
        )
        self.assertEqual(whitelist, [])

    def test_classify_for_base_update_discards_existing_after_whitelist(self):
        blocklist, whitelist, existing_discarded = classify_for_base_update(
            {"bet365.com", "instagram.com", "already.com"},
            {"already.com"},
        )
        self.assertEqual(blocklist, ["bet365.com"])
        self.assertEqual(whitelist[0]["domain"], "instagram.com")
        self.assertEqual(existing_discarded, {"already.com"})

    def test_classify_for_base_update_keeps_specific_url_when_only_specific_path_exists(self):
        blocklist, whitelist, existing_discarded = classify_for_base_update(
            {"erome.com", "erome.com/a/2qHOEUJi"},
            {"erome.com/a/1aaaaaaa"},
            set(),
        )
        self.assertEqual(blocklist, ["erome.com", "erome.com/a/2qHOEUJi"])
        self.assertEqual(whitelist, [])
        self.assertEqual(existing_discarded, set())

    def test_classify_for_base_update_discards_specific_url_when_domain_is_already_blocked(self):
        blocklist, whitelist, existing_discarded = classify_for_base_update(
            {"erome.com/a/2qHOEUJi"},
            {"erome.com"},
            {"erome.com"},
        )
        self.assertEqual(blocklist, [])
        self.assertEqual(whitelist, [])
        self.assertEqual(existing_discarded, {"erome.com/a/2qHOEUJi"})

    def test_confirm_pending_update_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "BASE_FILE_PATH": root / "base_atual.txt",
                "PENDING_UPDATE_PATH": root / "pendente.json",
                "OUTPUT_DIR": root / "output",
                "RUNS_DIR": root / "output" / "runs",
                "UPLOAD_DIR": root / "uploads",
                "AUDIT_DIR": root / "audits",
                "BACKUP_DIR": root / "backups",
                "LOG_DIR": root / "logs",
                "BASE_UPDATE_LOCK_PATH": root / "output" / "base_update.lock",
                "BACKUP_BEFORE_UPDATE": True,
            }
            config["OUTPUT_DIR"].mkdir()
            config["RUNS_DIR"].mkdir(parents=True)
            config["BASE_FILE_PATH"].write_text("a.com\n", encoding="utf-8")
            run_id = "20260101_120000_abcdef12"
            run_paths = get_run_file_paths(config, run_id)
            run_paths["run_dir"].mkdir(parents=True)
            run_paths["pending_update"].write_text('{"run_id": "20260101_120000_abcdef12", "domains": ["a.com", "b.com"]}', encoding="utf-8")

            first = confirm_pending_update(config, run_id=run_id)
            second = confirm_pending_update(config, run_id=run_id)

        self.assertEqual(first["added_count"], 1)
        self.assertEqual(second["added_count"], 0)

    def test_confirm_pending_update_preserves_existing_base_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "BASE_FILE_PATH": root / "base_atual.txt",
                "PENDING_UPDATE_PATH": root / "pendente.json",
                "OUTPUT_DIR": root / "output",
                "RUNS_DIR": root / "output" / "runs",
                "UPLOAD_DIR": root / "uploads",
                "AUDIT_DIR": root / "audits",
                "BACKUP_DIR": root / "backups",
                "LOG_DIR": root / "logs",
                "BASE_UPDATE_LOCK_PATH": root / "output" / "base_update.lock",
                "BACKUP_BEFORE_UPDATE": True,
            }
            config["OUTPUT_DIR"].mkdir()
            config["RUNS_DIR"].mkdir(parents=True)
            config["BASE_FILE_PATH"].write_text("a.com\nA.COM\n", encoding="utf-8")
            run_id = "20260101_120000_abcdef12"
            run_paths = get_run_file_paths(config, run_id)
            run_paths["run_dir"].mkdir(parents=True)
            run_paths["pending_update"].write_text('{"run_id": "20260101_120000_abcdef12", "domains": ["b.com"]}', encoding="utf-8")

            result = confirm_pending_update(config, run_id=run_id)
            entries = load_base_entries(config["BASE_FILE_PATH"])

        self.assertEqual(result["base_total"], 3)
        self.assertEqual(entries, ["a.com", "A.COM", "b.com"])

    def test_confirm_pending_update_accepts_approved_and_rejected_domains(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "BASE_FILE_PATH": root / "base" / "base_atual.txt",
                "REJECTED_FILE_PATH": root / "base" / "base_rejeitados.txt",
                "PENDING_UPDATE_PATH": root / "pendente.json",
                "OUTPUT_DIR": root / "output",
                "RUNS_DIR": root / "output" / "runs",
                "UPLOAD_DIR": root / "uploads",
                "AUDIT_DIR": root / "audits",
                "BACKUP_DIR": root / "backups",
                "LOG_DIR": root / "logs",
                "BASE_UPDATE_LOCK_PATH": root / "output" / "base_update.lock",
                "BACKUP_BEFORE_UPDATE": True,
            }
            config["BASE_FILE_PATH"].parent.mkdir(parents=True)
            config["OUTPUT_DIR"].mkdir()
            config["RUNS_DIR"].mkdir(parents=True)
            config["AUDIT_DIR"].mkdir()
            config["BASE_FILE_PATH"].write_text("a.com\n", encoding="utf-8")
            run_id = "20260101_120000_abcdef12"
            run_paths = get_run_file_paths(config, run_id)
            run_paths["run_dir"].mkdir(parents=True)
            run_paths["pending_update"].write_text(
                '{"run_id": "20260101_120000_abcdef12", "domains": ["a.com", "b.com", "c.com"]}',
                encoding="utf-8",
            )

            result = confirm_pending_update(
                config,
                run_id=run_id,
                approved_domains=["b.com"],
                rejected_domains=["c.com", "fora-do-pendente.com"],
            )
            entries = load_base_entries(config["BASE_FILE_PATH"])
            rejected_entries = load_base_entries(config["REJECTED_FILE_PATH"])
            with closing(sqlite3.connect(config["AUDIT_DIR"] / "auditoria.db")) as conn:
                rows = conn.execute("SELECT domain, run_id FROM rejected_domains ORDER BY domain").fetchall()

        self.assertEqual(result["added_count"], 1)
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(entries, ["a.com", "b.com"])
        self.assertEqual(rejected_entries, ["c.com"])
        self.assertEqual(rows, [("c.com", "20260101_120000_abcdef12")])

    def test_process_files_creates_run_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "BASE_FILE_PATH": root / "base" / "base_atual.txt",
                "WHITELIST_PATH": root / "output" / "whitelist.txt",
                "OUTPUT_PATH": root / "output" / "novos_dominios.txt",
                "REPORT_PATH": root / "output" / "relatorio.txt",
                "PENDING_UPDATE_PATH": root / "output" / "pendente_atualizacao.json",
                "OUTPUT_DIR": root / "output",
                "RUNS_DIR": root / "output" / "runs",
                "UPLOAD_DIR": root / "uploads",
                "AUDIT_DIR": root / "audits",
                "BACKUP_DIR": root / "backups",
                "LOG_DIR": root / "logs",
                "BASE_UPDATE_LOCK_PATH": root / "output" / "base_update.lock",
                "ENABLE_OCR": False,
                "OCR_LANGUAGE": "por+eng",
                "OCR_ONLY_IF_NO_DOMAINS": True,
                "BACKUP_BEFORE_UPDATE": True,
            }
            entrada = root / "uploads" / "entrada.txt"
            entrada.parent.mkdir(parents=True)
            entrada.write_text("bet365.com\ninstagram.com\n", encoding="utf-8")
            run_id = generate_run_id()

            summary = process_files([entrada], config, run_id)
            run_paths = get_run_file_paths(config, run_id)
            self.assertEqual(summary["run_id"], run_id)
            self.assertTrue(run_paths["blocklist"].exists())
            self.assertTrue(run_paths["whitelist"].exists())
            self.assertTrue(run_paths["report"].exists())
            self.assertTrue(run_paths["pending_update"].exists())
            self.assertTrue(run_paths["manifest"].exists())
            self.assertEqual(summary["artifacts"]["pending_update"], str(run_paths["pending_update"]))

    def test_confirm_pending_update_records_run_specific_updated_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "BASE_FILE_PATH": root / "base" / "base_atual.txt",
                "PENDING_UPDATE_PATH": root / "output" / "pendente_atualizacao.json",
                "OUTPUT_DIR": root / "output",
                "RUNS_DIR": root / "output" / "runs",
                "UPLOAD_DIR": root / "uploads",
                "AUDIT_DIR": root / "audits",
                "BACKUP_DIR": root / "backups",
                "LOG_DIR": root / "logs",
                "BASE_UPDATE_LOCK_PATH": root / "output" / "base_update.lock",
                "BACKUP_BEFORE_UPDATE": True,
            }
            config["BASE_FILE_PATH"].parent.mkdir(parents=True)
            config["OUTPUT_DIR"].mkdir()
            config["RUNS_DIR"].mkdir(parents=True)
            config["BASE_FILE_PATH"].write_text("a.com\n", encoding="utf-8")
            run_id = "20260101_120000_abcdef12"
            run_paths = get_run_file_paths(config, run_id)
            run_paths["run_dir"].mkdir(parents=True)
            run_paths["manifest"].write_text('{"run_id": "20260101_120000_abcdef12"}', encoding="utf-8")
            run_paths["pending_update"].write_text('{"run_id": "20260101_120000_abcdef12", "domains": ["b.com"]}', encoding="utf-8")

            result = confirm_pending_update(config, run_id=run_id)
            manifest = read_run_manifest(config, run_id)
            updated_path = run_updated_base_path(config, run_id)

        self.assertEqual(result["run_id"], run_id)
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["base_update"]["updated_base_file"], result["updated_base_file"])
        self.assertIsNotNone(updated_path)
        self.assertEqual(updated_path.name, result["updated_base_file"])

    def test_confirm_pending_update_uses_run_specific_updated_base_when_no_new_domains(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "BASE_FILE_PATH": root / "base" / "base_atual.txt",
                "PENDING_UPDATE_PATH": root / "output" / "pendente_atualizacao.json",
                "OUTPUT_DIR": root / "output",
                "RUNS_DIR": root / "output" / "runs",
                "UPLOAD_DIR": root / "uploads",
                "AUDIT_DIR": root / "audits",
                "BACKUP_DIR": root / "backups",
                "LOG_DIR": root / "logs",
                "BASE_UPDATE_LOCK_PATH": root / "output" / "base_update.lock",
                "BACKUP_BEFORE_UPDATE": True,
            }
            config["BASE_FILE_PATH"].parent.mkdir(parents=True)
            config["OUTPUT_DIR"].mkdir()
            config["RUNS_DIR"].mkdir(parents=True)
            config["BASE_FILE_PATH"].write_text("a.com\n", encoding="utf-8")
            run_id = "20260101_120000_abcdef12"
            run_paths = get_run_file_paths(config, run_id)
            run_paths["run_dir"].mkdir(parents=True)
            run_paths["pending_update"].write_text('{"run_id": "20260101_120000_abcdef12", "domains": ["a.com"]}', encoding="utf-8")

            first = confirm_pending_update(config, run_id=run_id, approved_domains=["a.com", "b.com"], rejected_domains=[])
            second = confirm_pending_update(config, run_id=run_id)

        self.assertEqual(first["updated_base_file"], second["updated_base_file"])

    def test_process_files_compares_against_authoritative_base_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "BASE_FILE_PATH": root / "base" / "base_atual.txt",
                "WHITELIST_PATH": root / "output" / "whitelist.txt",
                "OUTPUT_PATH": root / "output" / "novos_dominios.txt",
                "REPORT_PATH": root / "output" / "relatorio.txt",
                "PENDING_UPDATE_PATH": root / "output" / "pendente_atualizacao.json",
                "OUTPUT_DIR": root / "output",
                "RUNS_DIR": root / "output" / "runs",
                "UPLOAD_DIR": root / "uploads",
                "AUDIT_DIR": root / "audits",
                "BACKUP_DIR": root / "backups",
                "LOG_DIR": root / "logs",
                "BASE_UPDATE_LOCK_PATH": root / "output" / "base_update.lock",
                "ENABLE_OCR": False,
                "OCR_LANGUAGE": "por+eng",
                "OCR_ONLY_IF_NO_DOMAINS": True,
                "BACKUP_BEFORE_UPDATE": True,
            }
            config["BASE_FILE_PATH"].parent.mkdir(parents=True)
            config["BASE_FILE_PATH"].write_text("pc.537k7.com:8888\nbetl 8k.app\n", encoding="utf-8")
            entrada = root / "uploads" / "entrada.txt"
            entrada.parent.mkdir(parents=True)
            entrada.write_text("pc.537k7.com:8888\nbetl 8k.app\nnovoalvo.bet\n", encoding="utf-8")

            summary = process_files([entrada], config, generate_run_id())

        self.assertEqual(summary["existing_domains"], 2)
        self.assertEqual(summary["blocklist"], ["novoalvo.bet"])

    def test_lista_b_fixture_matches_expected_increment_count(self):
        fixture = Path("fixtures") / "Lista B.txt"
        self.assertTrue(fixture.exists())
        result = extract_txt(fixture)
        self.assertEqual(result.raw_count, 39598)
        self.assertEqual(len(result.domains), 39508)
        self.assertIn("5757.win", result.domains)

    def test_build_report(self):
        report = build_report([], {"a.com"}, set(), {"a.com"}, ["a.com"], [], set(), 0.1)
        self.assertIn("RELATORIO DE PROCESSAMENTO", report)
        self.assertIn("Total de dominios para bloqueio: 1", report)


if __name__ == "__main__":
    unittest.main()
