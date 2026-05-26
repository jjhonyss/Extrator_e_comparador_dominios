import tempfile
import unittest
from pathlib import Path

from processing import (
    build_report,
    classify_sensitive,
    compare_new_domains,
    classify_for_base_update,
    confirm_pending_update,
    extract_domains_from_lines,
    extract_domains_from_pdf_text,
    extract_domains_from_text,
    load_base_entries,
    load_domain_file,
    generate_run_id,
    get_run_file_paths,
    extract_txt,
    merge_wrapped_domain_lines,
    normalize_base_domain,
    normalize_domain,
    process_files,
    split_whitelist,
)


class ProcessingTests(unittest.TestCase):
    def test_normalize_domain(self):
        self.assertEqual(normalize_domain("https://www.Example.COM/path"), "www.example.com")
        self.assertEqual(normalize_domain("*.Gov.BR"), "gov.br")
        self.assertEqual(normalize_domain("www.bet"), "www.bet")
        self.assertIsNone(normalize_domain("invalid_domain"))
        self.assertIsNone(normalize_domain("example.123"))
        self.assertIsNone(normalize_domain("t.com"))

    def test_normalize_base_domain_is_strict_with_malformed_entries(self):
        self.assertEqual(normalize_base_domain("example.com"), "example.com")
        self.assertEqual(normalize_base_domain("www.example.com"), "www.example.com")
        self.assertIsNone(normalize_base_domain("example.com:2087"))
        self.assertIsNone(normalize_base_domain("example.com/path"))
        self.assertIsNone(normalize_base_domain("example.com."))

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

    def test_extract_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "entrada.txt"
            path.write_text("casino-online.net\ninstagram.com\n", encoding="utf-8")
            result = extract_txt(path)
        self.assertEqual(result.domains, {"casino-online.net", "instagram.com"})
        self.assertFalse(result.errors)

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
            run_id = "run_teste"
            run_paths = get_run_file_paths(config, run_id)
            run_paths["run_dir"].mkdir(parents=True)
            run_paths["pending_update"].write_text('{"run_id": "run_teste", "domains": ["a.com", "b.com"]}', encoding="utf-8")

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
            run_id = "run_teste"
            run_paths = get_run_file_paths(config, run_id)
            run_paths["run_dir"].mkdir(parents=True)
            run_paths["pending_update"].write_text('{"run_id": "run_teste", "domains": ["b.com"]}', encoding="utf-8")

            result = confirm_pending_update(config, run_id=run_id)
            entries = load_base_entries(config["BASE_FILE_PATH"])

        self.assertEqual(result["base_total"], 3)
        self.assertEqual(entries, ["a.com", "A.COM", "b.com"])

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

    def test_lista_b_fixture_matches_expected_increment_count(self):
        fixture = Path("fixtures") / "Lista B.txt"
        self.assertTrue(fixture.exists())
        result = extract_txt(fixture)
        self.assertEqual(result.raw_count, 39598)
        self.assertEqual(len(result.domains), 39598)
        self.assertIn("www.bet", result.domains)

    def test_build_report(self):
        report = build_report([], {"a.com"}, set(), {"a.com"}, ["a.com"], [], set(), 0.1)
        self.assertIn("RELATORIO DE PROCESSAMENTO", report)
        self.assertIn("Total de dominios para bloqueio: 1", report)


if __name__ == "__main__":
    unittest.main()
