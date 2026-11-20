"""Port events (contracts/events.yaml), normalised from what any adapter reported, so a consumer subscribes to a port
and never to a vendor. Pure functions: what an operation's input and output, or a callback's notification, mean as
events. Payloads carry ids, keys and statuses only, never a name, a document, a reading or a contact detail.

`d` is what the hub knows about the port object from its delivery log: caller_module, caller_reference, provider,
subject_key, object_id, person_id, account_link_id and refs (doc_kind, form_code, period, partner_id, format), merged
from the delivery at hand and the earlier one that created the object. An event whose identifying field is unknown is
not published (the caller learns the outcome from the delivery event instead)."""

from __future__ import annotations

from datetime import date, datetime

# The caller's key for each port's object, the adapter's id for it, and the input keys worth keeping (non-personal).
SUBJECT_KEY = {
    "meetings": "meeting_key",
    "certificate-issuance": "issuance_key",
    "academic-records": "batch_key",
    "regulatory-submission": "package_key",
    "inter-institution-records": "exchange_key",
    "wearable-data": "account_link_id",
}
OBJECT_ID = {
    "meetings": "meeting_id",
    "certificate-issuance": "issuance_id",
    "academic-records": "submission_id",
    "regulatory-submission": "package_id",
    "inter-institution-records": "exchange_id",
}
REF_KEYS = ("doc_kind", "award_kind", "form_code", "period", "partner_id", "format", "data_types", "from", "to")
_MAX = 200


def _s(value) -> str | None:
    if isinstance(value, str) and value:
        return value[:_MAX]
    if isinstance(value, datetime | date):
        return value.isoformat()
    return None


def _int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def subject_of(port: str, payload: dict) -> str | None:
    return _s(payload.get(SUBJECT_KEY.get(port, ""))) if isinstance(payload, dict) else None


def _id(value) -> str | None:
    """An id that fits the log's id columns (a uuid is 36 characters); anything longer is not kept."""
    value = _s(value)
    return value if value and len(value) <= 64 else None


def object_of(port: str, payload: dict | None) -> str | None:
    key = OBJECT_ID.get(port)
    return _id((payload or {}).get(key)) if key and isinstance(payload, dict) else None


def person_of(payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return None
    holder = payload.get("holder")
    candidate = holder.get("person_id") if isinstance(holder, dict) else None
    person = _id(candidate or payload.get("person_id"))
    return person if person and len(person) <= 36 else None


def refs_of(payload: dict) -> dict:
    out: dict = {}
    if not isinstance(payload, dict):
        return out
    for key in REF_KEYS:
        value = payload.get(key)
        if key == "data_types" and isinstance(value, list):
            out[key] = [v[:40] for v in value if isinstance(v, str)][:20]
        elif _s(value):
            out[key] = _s(value)
    return out


def _attendance(output: dict) -> tuple[list[dict], int]:
    matched, unmatched = [], 0
    for p in output.get("participants") or []:
        if not isinstance(p, dict):
            continue
        person = _s(p.get("person_id"))
        if not person:
            unmatched += 1
            continue
        intervals = [i for i in p.get("intervals") or [] if isinstance(i, dict)]
        joins = sorted(x for x in (_s(i.get("joined_at")) for i in intervals) if x)
        leaves = sorted(x for x in (_s(i.get("left_at")) for i in intervals) if x)
        matched.append(
            {
                "person_id": person,
                "role": _s(p.get("role")) or "attendee",
                "total_seconds": _int(p.get("total_seconds")) or 0,
                "first_joined_at": joins[0] if joins else None,
                "last_left_at": leaves[-1] if leaves else None,
            }
        )
    return matched, unmatched


def outbound_events(port: str, operation: str, payload: dict, output: dict, d: dict, today: date) -> list:
    """(event name without the module prefix, payload) for a port operation that succeeded."""
    refs = d.get("refs") or {}
    out: list[tuple[str, dict]] = []
    if port == "certificate-issuance" and operation in ("issue", "replace", "withdraw"):
        key, person = d.get("subject_key"), d.get("person_id")
        if not (key and person):
            return []
        base = {
            "issuance_key": key,
            "person_id": person,
            "doc_kind": refs.get("doc_kind") or "",
            "provider": d["provider"],
        }
        if operation == "withdraw":
            out.append(("certificate.withdrawn", base))
        else:
            out.append(("certificate.issued", {**base, "status": _s(output.get("status")) or "issued"}))
    elif port == "academic-records" and operation in (
        "publish_awards",
        "correct_awards",
        "publish_credits",
        "record_manual_upload",
    ):
        submission = _s(output.get("submission_id")) or d.get("object_id")
        if submission:
            kind = refs.get("award_kind") or ("credits" if operation == "publish_credits" else "awards")
            rejected = output.get("row_errors")
            out.append(
                (
                    "academic-record.submission-changed",
                    {
                        "submission_id": submission,
                        "caller_reference": d.get("caller_reference") or "",
                        "kind": kind,
                        "status": _s(output.get("status")) or "submitted",
                        "accepted_rows": _int(output.get("accepted_rows")),
                        "rejected_rows": len(rejected) if isinstance(rejected, list) else None,
                    },
                )
            )
    elif port == "regulatory-submission" and operation in ("prepare_package", "submit", "record_manual_submission"):
        package = _s(output.get("package_id")) or d.get("object_id")
        if package:
            base = {
                "package_id": package,
                "package_key": d.get("subject_key") or "",
                "form_code": refs.get("form_code") or "",
                "period": refs.get("period") or "",
            }
            if operation == "prepare_package":
                out.append(("regulatory-package.prepared", {**base, "status": _s(output.get("status")) or "prepared"}))
            else:
                manual = operation == "record_manual_submission"
                on = _s(payload.get("submitted_on")) if manual else None
                out.append(
                    (
                        "regulatory-package.submitted",
                        {**base, "channel": "manual" if manual else "api", "submitted_on": on or today.isoformat()},
                    )
                )
    elif port == "inter-institution-records" and operation in (
        "export_records",
        "send_records",
        "record_manual_delivery",
        "import_records",
    ):
        exchange = _s(output.get("exchange_id")) or d.get("object_id")
        if exchange:
            status = (
                {
                    "export_records": "exported",
                    "record_manual_delivery": "delivered_manually",
                    "import_records": "imported",
                }.get(operation)
                or _s(output.get("status"))
                or "sent"
            )
            out.append(
                (
                    "inter-institution-record.exchanged",
                    {
                        "exchange_id": exchange,
                        "exchange_key": d.get("subject_key") or exchange,
                        "partner_id": refs.get("partner_id") or "",
                        "direction": "inbound" if operation == "import_records" else "outbound",
                        "format": _s(output.get("format")) or refs.get("format") or "",
                        "status": status,
                    },
                )
            )
    elif port == "wearable-data" and operation == "sync":
        stored = (_int(output.get("stored")) or 0) + (_int(output.get("updated")) or 0)
        if stored and d.get("account_link_id") and d.get("person_id"):
            out.append(
                (
                    "wearable-data.received",
                    {
                        "account_link_id": d["account_link_id"],
                        "person_id": d["person_id"],
                        "provider": d["provider"],
                        "data_types": refs.get("data_types") or [],
                        "from": _s(output.get("from")) or refs.get("from"),
                        "to": _s(output.get("to")) or refs.get("to"),
                    },
                )
            )
    elif port == "meetings" and operation == "fetch_attendance":
        key = d.get("subject_key")
        if key:
            participants, unmatched = _attendance(output)
            out.append(
                (
                    "meeting-attendance.received",
                    {
                        "meeting_key": key,
                        "caller_module": d.get("caller_module") or "",
                        "complete": bool(output.get("complete")),
                        "participants": participants,
                        "unmatched_count": unmatched,
                    },
                )
            )
    return out


def inbound_events(port: str, kind: str, data: dict, d: dict) -> list:
    """(event name, payload) for one normalised notification from parse_inbound. Follow-up work (fetching attendance,
    syncing a wearable, ending a link) is the application's; this only says what to publish."""
    if port == "meetings":
        key = _s(data.get("meeting_key"))
        if not key:
            return []
        base = {"meeting_key": key, "caller_module": d.get("caller_module") or "", "provider": d["provider"]}
        if kind == "meeting_started":
            return [("meeting.started", {**base, "started_at": _s(data.get("started_at"))})]
        if kind == "meeting_ended":
            return [("meeting.ended", {**base, "ended_at": _s(data.get("ended_at"))})]
        if kind == "recording_ready" and _s(data.get("provider_recording_id")):
            return [
                (
                    "meeting-recording.available",
                    {
                        "meeting_key": key,
                        "caller_module": base["caller_module"],
                        "provider_recording_id": _s(data.get("provider_recording_id")),
                        "kind": _s(data.get("kind")) or "video",
                    },
                )
            ]
        return []  # participant_joined / participant_left are recorded, not published (docs/prd.md, open question 6)
    if port == "certificate-issuance" and kind == "document_pulled":
        key = _s(data.get("issuance_key"))
        if key and d.get("person_id"):
            return [
                (
                    "certificate.pulled",
                    {
                        "issuance_key": key,
                        "person_id": d["person_id"],
                        "provider": d["provider"],
                        "pulled_at": _s(data.get("pulled_at")),
                    },
                )
            ]
        return []
    if port == "academic-records" and kind == "submission_status_changed":
        submission = _s(data.get("submission_id"))
        if not submission:
            return []
        refs = d.get("refs") or {}
        return [
            (
                "academic-record.submission-changed",
                {
                    "submission_id": submission,
                    "caller_reference": d.get("caller_reference") or "",
                    "kind": refs.get("award_kind") or "awards",
                    "status": _s(data.get("status")) or "",
                    "accepted_rows": _int(data.get("accepted_rows")),
                    "rejected_rows": _int(data.get("rejected_rows")),
                },
            )
        ]
    if port == "inter-institution-records" and kind == "records_received":
        exchange = _s(data.get("exchange_id"))
        if not exchange:
            return []
        return [
            (
                "inter-institution-record.exchanged",
                {
                    "exchange_id": exchange,
                    "exchange_key": _s(data.get("exchange_key")) or exchange,
                    "partner_id": _s(data.get("partner_id")) or "",
                    "direction": "inbound",
                    "format": _s(data.get("format")) or "",
                    "status": "received",
                },
            )
        ]
    return []
