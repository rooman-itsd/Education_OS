"""How notification learns an organisation's display name without importing tenancy (repository rule 2).

Every template a consumer renders carries `organisation_name`, but an event envelope carries only
`organisation_id`, and notification may depend on identity alone.

The lookup is found on the `eos.organisation_directory` entry-point group, the same decoupling the messaging
adapter and the event consumers use. Deliberately NOT a hook assigned by `apps/backend` at startup, as
identity's `OrganisationHooks` is: the relay that delivers these events runs in its own process
(`python -m eos_event_bus`) and never executes the API's lifespan, so a hook wired there would be missing
exactly where the emails are sent. An entry point is found by any process that has the module installed.

Unwired, `name()` returns None and the consumer logs and sends nothing, rather than mailing somebody about
"The trial for  has ended"."""

from __future__ import annotations

from collections.abc import Callable
from importlib import metadata

from sqlalchemy.orm import Session

GROUP = "eos.organisation_directory"

_Lookup = Callable[[Session, str], "str | None"]
_lookup: _Lookup | None = None
_looked = False


def _discover() -> _Lookup | None:
    """The first registered lookup. One module (tenancy) owns organisations, so there is never a second."""
    for point in metadata.entry_points(group=GROUP):
        return point.load()
    return None


class OrganisationHooks:
    def name(self, db: Session, organisation_id: str) -> str | None:
        global _lookup, _looked
        if not _looked:
            _lookup, _looked = _discover(), True
        return _lookup(db, organisation_id) if _lookup else None


hooks = OrganisationHooks()


def reset_cache() -> None:
    """Tests that install or remove the entry point call this; nothing else needs it."""
    global _lookup, _looked
    _lookup, _looked = None, False
