"""Notices to committee members and complainants. platform/notification has no SDK in packages/sdk yet, so this is the
module's stand-in: it logs each notice and keeps the last ones in memory, as eos_core.notify does for email. Swap the
body of `send` for the notification SDK when it ships.

A notice carries the person id, the case number and a generic message, never case content (docs/prd.md
"Confidentiality and access")."""

from __future__ import annotations

import logging

log = logging.getLogger("eos.grievance.notify")
sent: list[dict] = []
MAX_KEPT = 200


def message(case_number: str) -> str:
    return f"There is an update on case {case_number}."


def send(organisation_id: str, person_ids: list[str], case_number: str) -> None:
    for person_id in dict.fromkeys(person_ids):
        sent.append(
            {
                "organisation_id": organisation_id,
                "person_id": person_id,
                "case_number": case_number,
                "message": message(case_number),
            }
        )
        log.info("notice to %s: %s", person_id, message(case_number))
    if len(sent) > MAX_KEPT:
        del sent[: len(sent) - MAX_KEPT]
