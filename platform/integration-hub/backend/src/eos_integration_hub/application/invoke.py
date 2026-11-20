"""The modules' calling surface: `invoke(port, operation, input, idempotency_key, caller_module, ...)`.

docs/prd.md proposes `sdk.integrations.invoke`. packages/sdk has no Python client of any platform service yet (its
src/ is empty, and platform/audit's pyproject notes it is not installable), so this is published the way modules reach
platform services today without importing them: an entry point, here `eos.integration_hub` / `invoke`.

    from importlib import metadata

    (point,) = metadata.entry_points(group="eos.integration_hub", name="invoke")
    invoke = point.load()
    result = invoke(port="meetings", operation="create_meeting", input={...},
                    idempotency_key="lms:class-session:<id>", caller_reference="<id>", caller_module="lms")

When packages/sdk gains its first client, `sdk.integrations.invoke` becomes a thin wrapper over this entry point and no
module changes its call."""

from __future__ import annotations

from .deliveries import invoke

__all__ = ["invoke"]
