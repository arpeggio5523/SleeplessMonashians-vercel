"""
Unit tests for the normalisation layer.

This is the module carrying most of the accuracy, so it gets the most tests.
Every new label variant or formatting quirk found in the data should arrive
here as a test case before the fix goes in.

    python -m pytest -q
"""
import pytest

from sdoc.core.normalize import (is_blank, norm_count, norm_party, norm_port,
                                 norm_weight, normalize)


# --------------------------------------------------------------------- blanks
@pytest.mark.parametrize("value", ["", "   ", "???", "N/A", "TBA", "TBC",
                                   "_______", "-", None])
def test_blanks_detected(value):
    assert is_blank(value)


@pytest.mark.parametrize("value", ["0", "SINGAPORE", "3"])
def test_real_values_not_blank(value):
    assert not is_blank(value)


# --------------------------------------------------------------------- party
def test_corporate_suffixes_ignored():
    assert norm_party("ACME CO., LTD") == norm_party("Acme Co Ltd")
    assert norm_party("GLOBEX PTE. LTD.") == norm_party("Globex Pte Ltd")
    assert norm_party("INITECH SDN BHD") == norm_party("Initech Sdn. Bhd.")


def test_address_lines_ignored():
    """Only the first line is the party name; the rest is address."""
    a = norm_party("ACME TRADING CO., LTD\n12 HARBOUR RD\nSINGAPORE 049315")
    assert a == norm_party("Acme Trading Co Ltd")


def test_pipe_separated_cells_truncated():
    """DOCX tables arrive as 'value | address'."""
    assert norm_party("ACME CO LTD | 12 HARBOUR RD") == norm_party("Acme Co Ltd")


def test_genuinely_different_parties_differ():
    assert norm_party("ACME CO., LTD") != norm_party("UMBRELLA CO., LTD")


# ---------------------------------------------------------------------- port
def test_port_code_is_ignored_not_used():
    """
    THE critical case. A port discrepancy changes the name and leaves the
    UN/LOCODE untouched. Comparing codes would hide 19 of 46 defects.
    """
    si = norm_port("MOMBASA, KENYA (KEMBA)")
    bl = norm_port("TUTICORIN, INDIA (KEMBA)")
    assert si != bl, "identical codes must not mask different port names"


def test_same_port_written_differently_matches():
    assert norm_port("SINGAPORE (SGSIN)") == norm_port("Singapore  (SGSIN)")
    assert norm_port("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)") == \
           norm_port("Port Klang (Westport), Malaysia (MYPKG)")


def test_port_without_code():
    assert norm_port("BUSAN, SOUTH KOREA") == "BUSAN SOUTH KOREA"


# --------------------------------------------------------------------- count
@pytest.mark.parametrize("raw,expected", [
    ("3", 3), ("3 x 40'HC", 3), ("12", 12), ("6 X 20GP", 6),
    ("THREE", 3), ("Four", 4), ("1,0", 10),
])
def test_container_counts(raw, expected):
    assert norm_count(raw) == expected


def test_count_unparseable_returns_none():
    assert norm_count("several") is None


# -------------------------------------------------------------------- weight
@pytest.mark.parametrize("raw,expected", [
    ("22,000 KG", 22000),
    ("22000", 22000),
    ("22000.00 kgs", 22000),
    ("131,322 KG", 131322),
])
def test_weight_kilograms(raw, expected):
    assert norm_weight(raw) == expected


def test_weight_pounds_converted():
    assert norm_weight("48501 LBS") == pytest.approx(22000, abs=2)


def test_weight_metric_tonnes_converted():
    assert norm_weight("22 MT") == 22000


def test_weight_same_value_different_format_matches():
    assert norm_weight("22,000 KG") == norm_weight("22000.00 kgs")


# ------------------------------------------------------------------ dispatch
def test_normalize_dispatches_by_field():
    assert normalize("gross_weight_kg", "22,000 KG") == 22000
    assert normalize("container_count", "3 x 40HC") == 3
    assert normalize("port_of_loading", "SINGAPORE (SGSIN)") == "SINGAPORE"


def test_normalize_blank_returns_none():
    for f in ("shipper", "container_count", "gross_weight_kg"):
        assert normalize(f, "???") is None
