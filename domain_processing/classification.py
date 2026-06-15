import re
from functools import lru_cache
from typing import Iterable

from .extraction import block_target_domain, is_specific_block_target


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
        "abta.org.br",
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

@lru_cache(maxsize=128)
def wildcard_to_regex(pattern: str) -> re.Pattern[str]:
    escaped = re.escape(pattern.lower()).replace(r"\*", r"[a-z0-9-]*")
    return re.compile(rf"(^|\.){escaped}$")


def classify_sensitive(domain: str) -> tuple[bool, str | None, str | None]:
    comparable = block_target_domain(domain) or domain
    for category, patterns in WHITELIST_PATTERNS.items():
        for pattern in patterns:
            normalized_pattern = pattern.lower()
            if "*" in normalized_pattern:
                if wildcard_to_regex(normalized_pattern).search(comparable):
                    return True, category, f"padrao wildcard: {pattern}"
                continue

            if comparable == normalized_pattern or comparable.endswith(f".{normalized_pattern}"):
                return True, category, f"padrao protegido: {pattern}"

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


def classify_for_base_update(
    extracted: Iterable[str],
    existing: Iterable[str],
    existing_domains: Iterable[str] | None = None,
) -> tuple[list[str], list[dict], set[str]]:
    candidates, whitelist = split_whitelist(extracted)
    existing_exact = set(existing)
    comparable_domains = set(existing if existing_domains is None else existing_domains)
    existing_discarded: set[str] = set()
    blocklist: list[str] = []

    for candidate in sorted(set(candidates)):
        candidate_domain = block_target_domain(candidate) or candidate
        if is_specific_block_target(candidate):
            if candidate in existing_exact or candidate_domain in comparable_domains:
                existing_discarded.add(candidate)
            else:
                blocklist.append(candidate)
            continue

        if candidate in comparable_domains or candidate in existing_exact:
            existing_discarded.add(candidate)
        else:
            blocklist.append(candidate)

    return blocklist, whitelist, existing_discarded
