from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject: str
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str | None = None
    scopes: frozenset[str] = frozenset()
    issuer: str
