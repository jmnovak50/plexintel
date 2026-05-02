from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


ALLOWED_SORA_MODELS = frozenset({"sora-2", "sora-2-pro"})
ALLOWED_SORA_SECONDS = frozenset({"4", "8", "12"})
ALLOWED_SORA_SIZES = frozenset({"1280x720", "720x1280", "1024x1792", "1792x1024"})

DEFAULT_SORA_MODEL = "sora-2"
DEFAULT_SORA_SIZE = "1280x720"
DEFAULT_SORA_SECONDS = "8"


class SoraConfigurationError(RuntimeError):
    pass


class SoraValidationError(ValueError):
    pass


class SoraAPIError(RuntimeError):
    pass


def get_default_sora_model() -> str:
    return os.getenv("SORA_DEFAULT_MODEL") or DEFAULT_SORA_MODEL


def get_default_sora_size() -> str:
    return os.getenv("SORA_DEFAULT_SIZE") or DEFAULT_SORA_SIZE


def get_default_sora_seconds() -> str:
    return os.getenv("SORA_DEFAULT_SECONDS") or DEFAULT_SORA_SECONDS


@dataclass(frozen=True)
class SoraVideoPayload:
    id: str
    status: str
    model: str | None = None
    progress: int | None = None
    size: str | None = None
    seconds: str | None = None
    error: Any | None = None


def normalize_sora_model(model: str | None) -> str:
    normalized = (model or get_default_sora_model()).strip()
    if normalized not in ALLOWED_SORA_MODELS:
        raise SoraValidationError(
            f"Unsupported Sora model '{normalized}'. Allowed values: {sorted(ALLOWED_SORA_MODELS)}"
        )
    return normalized


def normalize_sora_seconds(seconds: str | int | None) -> str:
    value = seconds if seconds is not None else get_default_sora_seconds()
    normalized = str(value).strip()
    if normalized not in ALLOWED_SORA_SECONDS:
        raise SoraValidationError(
            f"Unsupported Sora seconds '{normalized}'. Allowed values: {sorted(ALLOWED_SORA_SECONDS)}"
        )
    return normalized


def normalize_sora_size(size: str | None) -> str:
    normalized = (size or get_default_sora_size()).strip()
    if normalized not in ALLOWED_SORA_SIZES:
        raise SoraValidationError(
            f"Unsupported Sora size '{normalized}'. Allowed values: {sorted(ALLOWED_SORA_SIZES)}"
        )
    return normalized


def _serialize_error(error: Any) -> Any | None:
    if error is None:
        return None
    if hasattr(error, "model_dump"):
        return error.model_dump()
    if isinstance(error, dict):
        return error
    return str(error)


def _video_to_payload(video: Any) -> SoraVideoPayload:
    return SoraVideoPayload(
        id=str(getattr(video, "id")),
        status=str(getattr(video, "status")),
        model=getattr(video, "model", None),
        progress=getattr(video, "progress", None),
        size=getattr(video, "size", None),
        seconds=getattr(video, "seconds", None),
        error=_serialize_error(getattr(video, "error", None)),
    )


class SoraService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
        self._client = None

    def _get_client(self):
        if not self.api_key:
            raise SoraConfigurationError("OPENAI_API_KEY is not configured.")

        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise SoraConfigurationError("The openai package is not installed.") from exc

            self._client = OpenAI(api_key=self.api_key)

        return self._client

    def create_video(
        self,
        *,
        prompt: str,
        model: str | None,
        size: str | None,
        seconds: str | int | None,
    ) -> SoraVideoPayload:
        if not prompt or not prompt.strip():
            raise SoraValidationError("prompt is required.")

        normalized_model = normalize_sora_model(model)
        normalized_size = normalize_sora_size(size)
        normalized_seconds = normalize_sora_seconds(seconds)

        try:
            video = self._get_client().videos.create(
                prompt=prompt,
                model=normalized_model,
                size=normalized_size,
                seconds=normalized_seconds,
            )
        except SoraConfigurationError:
            raise
        except Exception as exc:
            raise SoraAPIError(f"Failed creating Sora video: {exc}") from exc

        return _video_to_payload(video)

    def get_video(self, video_id: str) -> SoraVideoPayload:
        if not video_id or "/" in video_id or "\\" in video_id:
            raise SoraValidationError("video_id is invalid.")

        try:
            video = self._get_client().videos.retrieve(video_id)
        except SoraConfigurationError:
            raise
        except Exception as exc:
            raise SoraAPIError(f"Failed retrieving Sora video: {exc}") from exc

        return _video_to_payload(video)

    def download_video_content(self, video_id: str) -> bytes:
        if not video_id or "/" in video_id or "\\" in video_id:
            raise SoraValidationError("video_id is invalid.")

        try:
            response = self._get_client().videos.download_content(video_id, variant="video")
            return response.read()
        except SoraConfigurationError:
            raise
        except Exception as exc:
            raise SoraAPIError(f"Failed downloading Sora video content: {exc}") from exc


def get_sora_service() -> SoraService:
    return SoraService()
