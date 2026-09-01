from datetime import datetime

from pydantic import BaseModel, Field


class CredentialStatus(BaseModel):
    identity_namespace: str = Field(exclude=True)
    source_issuer: str = Field(exclude=True)
    subject: str = Field(exclude=True)
    immich_user_id: str | None = None
    immich_email: str | None = None
    immich_name: str | None = None
    created_at: datetime
    updated_at: datetime
    validated_at_on_connect: datetime


class BrowserIdentity(BaseModel):
    identity_namespace: str
    issuer: str
    subject: str
    email: str | None = None
    preferred_username: str | None = None


class BrowserSession(BaseModel):
    identity: BrowserIdentity
    csrf_token: str = Field(repr=False)
    expires_at: datetime


class OAuthState(BaseModel):
    nonce: str = Field(repr=False)
    code_verifier: str = Field(repr=False)
    expires_at: datetime
