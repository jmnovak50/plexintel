from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AlbumSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    album_name: str | None = Field(default=None, alias="albumName")
    asset_count: int | None = Field(default=None, alias="assetCount")


class SharedLink(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    type: str
    description: str | None = None
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    allow_download: bool | None = Field(default=None, alias="allowDownload")
    allow_upload: bool | None = Field(default=None, alias="allowUpload")
    show_metadata: bool | None = Field(default=None, alias="showMetadata")
    album: AlbumSummary | None = None
    assets: list[dict[str, Any]] = Field(default_factory=list)

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        reference = now or datetime.now(timezone.utc)
        expiry = self.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry <= reference


class TimelineBucket(BaseModel):
    model_config = ConfigDict(extra="allow")
    time_bucket: str = Field(alias="timeBucket")
    count: int = 0


class ImagePayload(BaseModel):
    data: bytes
    mime_type: str


class SharedAlbumResult(BaseModel):
    shared_link: dict[str, Any]
    album: dict[str, Any]
    album_id: str
    asset_count: int
    expiration: datetime | None
    permissions: dict[str, bool | None]


class AuthenticatedUser(BaseModel):
    issuer: str
    sub: str
    email: str | None = None
    preferred_username: str | None = None
    scopes: list[str] = Field(default_factory=list)


class PrivateImmichCredential(BaseModel):
    kind: Literal["api_key", "session"]
    token: str = Field(repr=False)


class ShareCredential(BaseModel):
    kind: Literal["share"] = "share"
    token: str = Field(repr=False)


ImmichCredential = PrivateImmichCredential | ShareCredential
