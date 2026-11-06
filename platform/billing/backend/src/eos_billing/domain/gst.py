"""GST rules for a tax invoice, as pure functions: no database, no clock, no environment.

- GSTIN: 15 characters, state code + PAN + entity number + "Z" + a check character (validated, not just matched).
- Place of supply decides the tax: the supplier's state equal to the place of supply is an intra-state supply
  (CGST + SGST, each half the rate); any other is inter-state (IGST, the whole rate).
- Money is Decimal throughout, rounded half up to the paisa at each tax head. CGST and SGST are always equal, so the
  invoice never shows a one-paisa difference between them and the tax total is exactly cgst + sgst.
- The financial year runs 1 April to 31 March, read in Indian Standard Time (the date on the invoice is the Indian date).
- The invoice number is at most 16 characters (rule 46 of the CGST Rules): PREFIX/YY-YY/NNNNNN, numbers never reused.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

PAISA = Decimal("0.01")
IST = timedelta(hours=5, minutes=30)
MAX_NUMBER_LENGTH = 16

# State and union territory codes used in a GSTIN (the first two digits), and "place of supply" names.
STATES: dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "28": "Andhra Pradesh (before the division)",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
}

_GSTIN = re.compile(r"^(\d{2})([A-Z]{5}\d{4}[A-Z])([1-9A-Z])Z([0-9A-Z])$")
_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_SAC = re.compile(r"^99\d{4}$")
_PREFIX = re.compile(r"^[A-Z0-9][A-Z0-9/-]*$")


class GstError(ValueError):
    """Bad GST input: a message safe to show to the person who typed it."""


def _check_character(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        value = _ALPHABET.index(ch) * (2 if i % 2 else 1)
        total += value // 36 + value % 36
    return _ALPHABET[(36 - total % 36) % 36]


def normalise_gstin(raw: str | None) -> str | None:
    """Upper-case and trimmed, or None for blank. Does not validate."""
    text = (raw or "").strip().upper()
    return text or None


def validate_gstin(raw: str | None) -> str:
    """The normalised GSTIN, or GstError: wrong format, unknown state code or a check character that does not match."""
    gstin = normalise_gstin(raw)
    if gstin is None:
        raise GstError("GSTIN is empty")
    m = _GSTIN.match(gstin)
    if not m:
        raise GstError("GSTIN must be 15 characters: 2-digit state code, PAN, entity number, Z and a check character")
    if m.group(1) not in STATES:
        raise GstError(f"GSTIN has an unknown state code {m.group(1)}")
    if _check_character(gstin[:14]) != gstin[14]:
        raise GstError("GSTIN check character does not match")
    return gstin


def state_code(gstin: str) -> str:
    return gstin[:2]


def validate_state_code(raw: str | None) -> str:
    code = (raw or "").strip()
    if code not in STATES:
        raise GstError(f"unknown state code {code!r}")
    return code


def validate_sac(raw: str) -> str:
    code = (raw or "").strip()
    if not _SAC.match(code):
        raise GstError("SAC must be six digits starting 99")
    return code


def money(value: Decimal | int | str | float) -> Decimal:
    """Exact decimal at two places, rounded half up. A float is read through its repr, never its binary value."""
    return (value if isinstance(value, Decimal) else Decimal(str(value))).quantize(PAISA, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Tax:
    scheme: str  # "intra" (CGST + SGST) | "inter" (IGST)
    rate: Decimal  # percent, e.g. 18
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal

    @property
    def total_tax(self) -> Decimal:
        return self.cgst + self.sgst + self.igst

    @property
    def total(self) -> Decimal:
        return self.taxable_value + self.total_tax


def compute_tax(taxable_value: Decimal | int | str | float, rate: Decimal | int | str, *, intra_state: bool) -> Tax:
    value, rate = money(taxable_value), Decimal(str(rate))
    if value < 0:
        raise GstError("taxable value cannot be negative")
    if not Decimal(0) <= rate <= Decimal(100):
        raise GstError("GST rate must be between 0 and 100 percent")
    zero = Decimal("0.00")
    if intra_state:
        half = money(value * rate / Decimal(200))
        return Tax("intra", rate, value, half, half, zero)
    return Tax("inter", rate, value, zero, zero, money(value * rate / Decimal(100)))


def place_of_supply(recipient_state: str | None, supplier_state: str) -> str:
    """The recipient's state when known; otherwise the supplier's (the location of the recipient is the place of
    supply when an address is on record, and the location of the supplier when it is not: section 12(2) IGST Act)."""
    return recipient_state or supplier_state


def financial_year(moment: datetime) -> str:
    """The Indian financial year of an instant, as 'YY-YY': 31 March 2027 23:59 IST is '26-27', 1 April 00:00 IST
    is '27-28'. A naive datetime is read as UTC."""
    local = (moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)) + IST
    start = local.year if local.month >= 4 else local.year - 1
    return f"{start % 100:02d}-{(start + 1) % 100:02d}"


def validate_prefix(prefix: str) -> str:
    text = (prefix or "").strip().upper()
    if not _PREFIX.match(text):
        raise GstError("invoice prefix may hold only letters, digits, '/' and '-'")
    if len(text) + len("/26-27/000001") > MAX_NUMBER_LENGTH:
        raise GstError(f"invoice prefix is too long: a number must stay within {MAX_NUMBER_LENGTH} characters")
    return text


def invoice_number(prefix: str, fy: str, sequence: int) -> str:
    """PREFIX/YY-YY/NNNNNN, within 16 characters. The sequence restarts at 1 each financial year."""
    if sequence < 1 or sequence > 999999:
        raise GstError("invoice sequence is exhausted for this financial year")
    number = f"{validate_prefix(prefix)}/{fy}/{sequence:06d}"
    assert len(number) <= MAX_NUMBER_LENGTH
    return number
