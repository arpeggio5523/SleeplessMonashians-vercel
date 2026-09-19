"""
normalize.py — make two differently-written values comparable.

Owner: I (intelligence). This is pure functions with no I/O, so it is the
easiest module to unit-test and the one most worth testing. See
tests/test_normalize.py.

This module carries most of the accuracy. The brief's third named problem
is that "the same information can look different"; this is the answer to it.
"""
from __future__ import annotations

import re
from typing import Optional

# Values that mean "not filled in" rather than a real value.
BLANKS = {"", "???", "N/A", "N.A.", "NA", "TBA", "TBC", "-", "--", "TO BE ADVISED"}

# Corporate suffixes carry no identifying information and are written
# inconsistently across the two documents.
SUFFIXES = r"\b(CO|COMPANY|LIMITED|LTD|PVT|PTE|SDN|BHD|LLC|INC|INCORPORATED|GMBH|FZE|FZ|CORP|CORPORATION|PTY|PLC|SA|NV|BV|AG|SRL|SPA)\b"

NUMBER_WORDS = {
    "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6,
    "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10, "ELEVEN": 11, "TWELVE": 12,
}

LB_TO_KG = 0.45359237


def is_blank(raw: Optional[str]) -> bool:
    """
    True when a value is absent or a placeholder rather than real data.

    Placeholders in this data include fill-in-the-blank runs such as
    '____MT' and '_______', which must NOT be compared as if they were
    values — doing so invents discrepancies.
    """
    if raw is None:
        return True
    s = str(raw).strip()
    if re.search(r"_{3,}", s):          # '____MT', '_______'
        return True
    s = s.strip("_").strip()
    return s.upper() in BLANKS or not s


def norm_party(v: Optional[str]) -> Optional[str]:
    """
    Company names. 'ACME CO., LTD' and 'Acme Co Ltd' must compare equal.
    Only the first line is used — the rest is address, which the two
    documents format differently and which is not one of the seven fields.
    """
    if v is None:
        return None
    v = str(v).split("|")[0].split("\n")[0].upper()
    v = re.sub(r"[.,]", " ", v)
    v = re.sub(SUFFIXES, " ", v)
    v = re.sub(r"[^A-Z0-9 ]", " ", v)
    return " ".join(v.split()) or None


def norm_port(v: Optional[str]) -> Optional[str]:
    """
    Ports. CRITICAL: compare the NAME and discard the UN/LOCODE.

    When a port discrepancy exists the name changes and the code is left
    untouched, e.g.

        SI: MOMBASA, KENYA (KEMBA)
        BL: TUTICORIN, INDIA (KEMBA)

    Normalising to the code makes every port discrepancy invisible —
    19 of the 46 scoring emails. Do not "improve" this by using the code.
    """
    if v is None:
        return None
    v = re.sub(r"\([A-Z]{5}\)", "", str(v))      # drop the UN/LOCODE
    v = v.upper()
    v = re.sub(r"[^A-Z0-9 ]", " ", v)
    return " ".join(v.split()) or None


def norm_count(v) -> Optional[int]:
    """Container counts: '3', '3 x 40HC', 'THREE' -> 3."""
    if v is None:
        return None
    s = str(v).upper().replace(",", "")
    for word, n in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", s):
            return n
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def norm_weight(v) -> Optional[int]:
    """
    Gross weight -> whole kilograms.
    Handles '22,000 KG', '22000.00 kgs', '48501 LBS', '22 MT'.
    """
    if v is None:
        return None
    s = str(v).upper().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    n = float(m.group(1))
    if "LB" in s:
        n *= LB_TO_KG
    if re.search(r"\bMT\b|TONNE|\bTON\b", s):
        n *= 1000
    return round(n)


NORMALIZERS = {
    "shipper": norm_party,
    "consignee": norm_party,
    "notify_party": norm_party,
    "port_of_loading": norm_port,
    "port_of_discharge": norm_port,
    "container_count": norm_count,
    "gross_weight_kg": norm_weight,
}


def normalize(field: str, raw: Optional[str]):
    """Normalise one raw value for one field. Returns None if unusable."""
    if is_blank(raw):
        return None
    fn = NORMALIZERS.get(field)
    return fn(raw) if fn else raw
