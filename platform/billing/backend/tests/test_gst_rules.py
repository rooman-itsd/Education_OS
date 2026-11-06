"""GST rules as pure functions: GSTIN format and check character, intra/inter-state tax, rounding, financial year
and the invoice number. No database."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from eos_billing.domain import gst

MAHARASHTRA = "27AAPFU0939F1ZV"  # a real-format GSTIN with a correct check character
DELHI = "07AAGFF2194N1Z1"
KARNATAKA = "29AABCT1332L1ZA"
TAMIL_NADU = "33AAACC1206D1ZN"


@pytest.mark.parametrize("gstin", [MAHARASHTRA, DELHI, KARNATAKA, TAMIL_NADU])
def test_valid_gstins_pass(gstin):
    assert gst.validate_gstin(gstin) == gstin


def test_gstin_is_trimmed_and_upper_cased():
    assert gst.validate_gstin(f"  {MAHARASHTRA.lower()} ") == MAHARASHTRA


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        None,
        "27AAPFU0939F1Z",  # 14 characters
        "27AAPFU0939F1ZVV",  # 16 characters
        "27AAPFU0939F1AV",  # 14th character must be Z
        "27AAPFU09391FZV",  # PAN shape wrong (digit where a letter belongs)
        "AAAPFU0939F1ZV0",  # no state code
        "27AAPFU0939F0ZV",  # entity number 0 is not allowed
        "27AAPFU0939F1Z-",  # not alphanumeric
    ],
)
def test_bad_gstin_format_is_refused(bad):
    with pytest.raises(gst.GstError):
        gst.validate_gstin(bad)


def test_unknown_state_code_is_refused():
    # 25 is retired and 00, 39 and 99 are not state codes in a GSTIN; built with a correct check character.
    for code in ("00", "25", "39", "99"):
        body = f"{code}AAPFU0939F1Z"
        gstin = body + gst._check_character(body)
        with pytest.raises(gst.GstError, match="state code"):
            gst.validate_gstin(gstin)


def test_wrong_check_character_is_refused():
    with pytest.raises(gst.GstError, match="check character"):
        gst.validate_gstin("27AAPFU0939F1ZW")  # right shape, last character one off
    with pytest.raises(gst.GstError, match="check character"):
        gst.validate_gstin("27AAPFU0939G1ZV")  # a changed digit elsewhere breaks the checksum


def test_a_single_changed_character_never_validates():
    for i in range(14):
        original = MAHARASHTRA[i]
        for ch in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if ch == original or i in (13,):
                continue
            candidate = MAHARASHTRA[:i] + ch + MAHARASHTRA[i + 1 :]
            try:
                gst.validate_gstin(candidate)
            except gst.GstError:
                continue
            raise AssertionError(f"{candidate} validated")


def test_state_code_and_sac_validation():
    assert gst.state_code(KARNATAKA) == "29"
    assert gst.validate_state_code("33") == "33"
    with pytest.raises(gst.GstError):
        gst.validate_state_code("99")
    assert gst.validate_sac("998315") == "998315"
    for bad in ("", "99831", "9983150", "123456", "99831A"):
        with pytest.raises(gst.GstError):
            gst.validate_sac(bad)


def test_intra_state_splits_into_equal_cgst_and_sgst():
    tax = gst.compute_tax("24999", "18", intra_state=True)
    assert tax.scheme == "intra"
    assert (tax.cgst, tax.sgst, tax.igst) == (Decimal("2249.91"), Decimal("2249.91"), Decimal("0.00"))
    assert tax.total_tax == Decimal("4499.82")
    assert tax.total == Decimal("29498.82")


def test_inter_state_is_one_igst_line():
    tax = gst.compute_tax("24999", "18", intra_state=False)
    assert tax.scheme == "inter"
    assert (tax.cgst, tax.sgst, tax.igst) == (Decimal("0.00"), Decimal("0.00"), Decimal("4499.82"))
    assert tax.total == Decimal("29498.82")


def test_rounding_is_half_up_at_each_head():
    # 100.05 at 18%: each half is 9.0045 (rounds down to 9.00); the whole is 18.009 (rounds up to 18.01)
    intra = gst.compute_tax("100.05", "18", intra_state=True)
    assert (intra.cgst, intra.sgst) == (Decimal("9.00"), Decimal("9.00"))
    assert gst.compute_tax("100.05", "18", intra_state=False).igst == Decimal("18.01")
    # exactly half a paisa goes up: 0.25 at 18% is 0.045 whole -> 0.05; 0.50 gives 0.045 per half -> 0.05
    assert gst.compute_tax("0.25", "18", intra_state=False).igst == Decimal("0.05")
    assert gst.compute_tax("0.50", "18", intra_state=True).cgst == Decimal("0.05")
    # the amount may arrive as a float; it is read as written, not as its binary value
    assert gst.compute_tax(0.1 + 0.2, "18", intra_state=False).igst == Decimal("0.05")
    assert gst.compute_tax("1", "5", intra_state=True).total == Decimal("1.06")


def test_cgst_and_sgst_are_always_equal_and_sum_to_the_tax_total():
    for cents in range(1, 400):
        tax = gst.compute_tax(Decimal(cents) / 100, "18", intra_state=True)
        assert tax.cgst == tax.sgst
        assert tax.total_tax == tax.cgst + tax.sgst
        assert tax.total == tax.taxable_value + tax.total_tax


def test_zero_rate_and_bad_input():
    assert gst.compute_tax("500", "0", intra_state=True).total == Decimal("500.00")
    for args in (("-1", "18"), ("100", "-1"), ("100", "101")):
        with pytest.raises(gst.GstError):
            gst.compute_tax(*args, intra_state=True)


def test_place_of_supply_falls_back_to_the_supplier_when_the_recipient_has_no_state():
    assert gst.place_of_supply("29", "27") == "29"
    assert gst.place_of_supply(None, "27") == "27"


def test_financial_year_turns_over_at_midnight_indian_time():
    ist = lambda *a: datetime(*a, tzinfo=UTC)  # noqa: E731  (UTC instants; IST is UTC+5:30)
    # 31 March 2027, 23:59 IST = 18:29 UTC -> still 26-27
    assert gst.financial_year(ist(2027, 3, 31, 18, 29, 59)) == "26-27"
    # 1 April 2027, 00:00 IST = 18:30 UTC on 31 March -> 27-28
    assert gst.financial_year(ist(2027, 3, 31, 18, 30, 0)) == "27-28"
    assert gst.financial_year(ist(2027, 4, 1, 0, 0, 0)) == "27-28"
    assert gst.financial_year(ist(2027, 1, 15)) == "26-27"
    assert gst.financial_year(ist(2026, 4, 1, 12)) == "26-27"
    assert gst.financial_year(ist(2026, 12, 31, 18, 30)) == "26-27"
    assert gst.financial_year(datetime(2027, 3, 31, 18, 30)) == "27-28"  # naive is UTC


def test_invoice_number_fits_sixteen_characters_and_rejects_overflow():
    assert gst.invoice_number("EOS", "26-27", 1) == "EOS/26-27/000001"
    assert len(gst.invoice_number("EOS", "26-27", 999999)) == 16
    for seq in (0, -1, 1_000_000):
        with pytest.raises(gst.GstError):
            gst.invoice_number("EOS", "26-27", seq)
    assert gst.validate_prefix("a-1") == "A-1"
    for bad in ("", "EOSX", "E S", "E*S"):
        with pytest.raises(gst.GstError):
            gst.validate_prefix(bad)
