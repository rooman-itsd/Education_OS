"""Pure functions: normalisation, hashing and signing. Nothing here touches the network or the database."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from datetime import UTC, date, datetime, timedelta, timezone
from xml.etree import ElementTree

IST = timezone(timedelta(hours=5, minutes=30))
URI_SAFE = re.compile(r"[^A-Za-z0-9._-]")
MAX_XML_BYTES = 262_144


def normalise_name(value: str) -> str:
    """Case, accents, punctuation and spacing do not decide whether two names are the same person's."""
    text = unicodedata.normalize("NFKC", value).casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE).replace("_", " ")
    return " ".join(text.split())


def normalise_value(value: object) -> str:
    return "".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def parse_dob(value: str | None) -> date | None:
    """DigiLocker sends DDMMYYYY; other common spellings are accepted. None when it is not a date."""
    if not value:
        return None
    text = value.strip()
    for fmt in ("%d%m%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def uri_for(issuer_id: str, doc_type: str, document_number: str) -> str:
    """<IssuerId>-<DocType>-<DocId>. The document number is made URI-safe; a collision is caught by the unique
    constraint on (organisation, uri) and reported as a conflict."""
    return f"{issuer_id}-{doc_type}-{URI_SAFE.sub('_', document_number)}"


def search_key_hash(pepper: str, organisation_id: str, doc_type: str, keys: dict[str, object]) -> str:
    """A keyed hash of the doc type's search values, canonical in key order and case. Without the pepper a roll
    number cannot be recovered from the database by guessing."""
    canonical = "\n".join(f"{k.strip().casefold()}={normalise_value(v)}" for k, v in sorted(keys.items()))
    msg = f"{organisation_id}|{doc_type}|{canonical}".encode()
    return hmac.new(pepper.encode(), msg, hashlib.sha256).hexdigest()


def keyhash(api_key: str, ts: str) -> str:
    """Pull API: SHA-256 of the issuer API key followed by the request timestamp, hex."""
    return hashlib.sha256((api_key + ts).encode()).hexdigest()


def keyhash_ok(api_key: str, ts: str, presented: str | None) -> bool:
    return bool(presented) and hmac.compare_digest(keyhash(api_key, ts), presented.strip().lower())


def parse_ts(value: str | None) -> datetime | None:
    """A request timestamp. DigiLocker writes ISO 8601 in IST; a timestamp without a zone is read as IST."""
    if not value or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return (parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed).astimezone(UTC)


def push_hmac(client_secret: str, fields: list[str]) -> str:
    """Push URI: SHA-256 over the client secret followed by the request fields in the order given by the spec."""
    return hashlib.sha256((client_secret + "".join(fields)).encode()).hexdigest()


def file_hmac(client_secret: str, content: bytes) -> str:
    """Requester file fetch: HMAC-SHA256 of the content keyed by the client secret, hex."""
    return hmac.new(client_secret.encode(), content, hashlib.sha256).hexdigest()


def parse_xml(raw: bytes) -> ElementTree.Element:
    """Parse a provider request. Bounded, and a DOCTYPE or entity declaration is refused outright, so no entity
    expansion attack can reach the parser."""
    if len(raw) > MAX_XML_BYTES:
        raise ValueError("request too large")
    try:
        head = raw.decode("utf-8").lower()  # UTF-8 only: another encoding could hide a DOCTYPE from this check
    except UnicodeDecodeError as e:
        raise ValueError("requests must be UTF-8") from e
    if "<!doctype" in head or "<!entity" in head:
        raise ValueError("DTDs are not accepted")
    try:
        return ElementTree.fromstring(raw)  # noqa: S314  no DTD can reach the parser (checked above)
    except ElementTree.ParseError as e:
        raise ValueError("not well-formed XML") from e


_XML_NAME = re.compile(r"[^A-Za-z0-9_]")


def data_xml(doc_type: str, data: dict) -> str:
    """The machine-readable copy of a document: a flat <Certificate> with one element per field."""
    root = ElementTree.Element("Certificate", {"type": doc_type})
    for key in sorted(data):
        name = _XML_NAME.sub("_", key)
        if not name or not (name[0].isalpha() or name[0] == "_"):
            name = f"f_{name}"
        ElementTree.SubElement(root, name).text = "" if data[key] is None else str(data[key])
    return ElementTree.tostring(root, encoding="unicode")
