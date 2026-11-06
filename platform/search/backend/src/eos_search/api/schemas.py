"""Request bodies. Query parameters are bounded in the route signatures (api/router.py) and again in the service."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..domain.declarations import MODULE_RE, TYPE_KEY_RE


class ReindexIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str = Field(min_length=2, max_length=64, pattern=MODULE_RE.pattern)
    type: str | None = Field(default=None, max_length=130, pattern=TYPE_KEY_RE.pattern)
    organisation_id: UUID | None = None
