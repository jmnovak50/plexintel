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


def principal_from_validated_identity(
    *,
    namespace: str,
    default_tenant_id: str,
    subject: str,
    issuer: str,
    email: str | None = None,
    scopes: frozenset[str] = frozenset(),
) -> Principal:
    if not subject:
        raise PermissionError("authenticated subject is unavailable")
    return Principal(
        subject=subject,
        user_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{namespace}:user:{subject}"),
        tenant_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{namespace}:tenant:{default_tenant_id}"),
        email=email,
        scopes=scopes,
        issuer=issuer,
    )
