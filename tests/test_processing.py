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
    extract_domains_from_text,
    load_base_entries,
    extract_txt,
    merge_wrapped_domain_lines,
    normalize_domain,
    split_whitelist,
)


class ProcessingTests(unittest.TestCase):
    def test_normalize_domain(self):
        self.assertEqual(normalize_domain("https://www.Example.COM/path"), "example.com")
        self.assertEqual(normalize_domain("*.Gov.BR"), "gov.br")
        self.assertIsNone(normalize_domain("invalid_domain"))
        self.assertIsNone(normalize_domain("example.123"))
        self.assertIsNone(normalize_domain("t.com"))

    def test_extract_domains_from_text_deduplicates(self):
        text = "Bloquear https://www.bet365.com e bet365.com. Preservar anatel.gov.br"
        domains, duplicates = extract_domains_from_text(text)
        self.assertIn("bet365.com", domains)
        self.assertIn("anatel.gov.br", domains)
        self.assertGreaterEqual(duplicates, 1)

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

    def test_split_whitelist(self):
        blocklist, whitelist = split_whitelist({"bet365.com", "bancobrasil.com.br"})
        self.assertEqual(blocklist, ["bet365.com"])
        self.assertEqual(whitelist[0]["category"], "BANCOS")

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
                "UPLOAD_DIR": root / "uploads",
                "AUDIT_DIR": root / "audits",
                "BACKUP_DIR": root / "backups",
                "LOG_DIR": root / "logs",
                "BACKUP_BEFORE_UPDATE": True,
            }
            config["OUTPUT_DIR"].mkdir()
            config["BASE_FILE_PATH"].write_text("a.com\n", encoding="utf-8")
            config["PENDING_UPDATE_PATH"].write_text('{"domains": ["a.com", "b.com"]}', encoding="utf-8")

            first = confirm_pending_update(config)
            second = confirm_pending_update(config)

        self.assertEqual(first["added_count"], 1)
        self.assertEqual(second["added_count"], 0)

    def test_confirm_pending_update_preserves_existing_base_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "BASE_FILE_PATH": root / "base_atual.txt",
                "PENDING_UPDATE_PATH": root / "pendente.json",
                "OUTPUT_DIR": root / "output",
                "UPLOAD_DIR": root / "uploads",
                "AUDIT_DIR": root / "audits",
                "BACKUP_DIR": root / "backups",
                "LOG_DIR": root / "logs",
                "BACKUP_BEFORE_UPDATE": True,
            }
            config["OUTPUT_DIR"].mkdir()
            config["BASE_FILE_PATH"].write_text("a.com\nA.COM\n", encoding="utf-8")
            config["PENDING_UPDATE_PATH"].write_text('{"domains": ["b.com"]}', encoding="utf-8")

            result = confirm_pending_update(config)
            entries = load_base_entries(config["BASE_FILE_PATH"])

        self.assertEqual(result["base_total"], 3)
        self.assertEqual(entries, ["a.com", "A.COM", "b.com"])

    def test_build_report(self):
        report = build_report([], {"a.com"}, set(), {"a.com"}, ["a.com"], [], set(), 0.1)
        self.assertIn("RELATORIO DE PROCESSAMENTO", report)
        self.assertIn("Total de dominios para bloqueio: 1", report)


if __name__ == "__main__":
    unittest.main()
