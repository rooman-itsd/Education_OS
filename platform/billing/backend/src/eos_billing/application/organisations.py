"""How billing learns an organisation's display name without importing tenancy (repository rule 2), for the super
admin's reports. The same `eos.organisation_directory` entry point platform/notification uses
(eos_notification.application.organisations): tenancy publishes `organisation_name(db, organisation_id)` there.
Unwired, `name()` returns None and the report shows the organisation without a name."""

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


def name(db: Session, organisation_id: str) -> str | None:
    global _lookup, _looked
    if not _looked:
        _lookup, _looked = _discover(), True
    return _lookup(db, organisation_id) if _lookup else None


def reset_cache() -> None:
    """Tests that install or remove the entry point call this; nothing else needs it."""
    global _lookup, _looked
    _lookup, _looked = None, False
