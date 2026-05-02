from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.services.sora_service import (
    SoraAPIError,
    SoraConfigurationError,
    SoraService,
    SoraValidationError,
    get_default_sora_model,
    get_default_sora_seconds,
    get_default_sora_size,
    get_sora_service,
)
from api.services.sora_storage_service import (
    SoraStorageError,
    build_stream_url,
    get_local_video_path,
    save_video_content,
)


router = APIRouter()


class VideoCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str = Field(default_factory=get_default_sora_model)
    size: str = Field(default_factory=get_default_sora_size)
    seconds: str | int = Field(default_factory=get_default_sora_seconds)
    openwebui_user_id: str | None = None


class VideoDownloadRequest(BaseModel):
    openwebui_user_id: str | None = None


class VideoCreateResponse(BaseModel):
    id: str
    status: str
    model: str | None = None
    progress: int | None = None
    size: str | None = None
    seconds: str | None = None
    error: Any | None = None


class VideoStoredResponse(BaseModel):
    video_id: str
    status: str
    stored: bool
    file_path: str | None = None
    stream_url: str | None = None


def _service_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, SoraValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, SoraConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, SoraAPIError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def _response_from_payload(payload) -> VideoCreateResponse:
    return VideoCreateResponse(
        id=payload.id,
        status=payload.status,
        model=payload.model,
        progress=payload.progress,
        size=payload.size,
        seconds=payload.seconds,
        error=payload.error,
    )


def _store_completed_video(
    *,
    video_id: str,
    openwebui_user_id: str | None,
    sora_service: SoraService,
) -> VideoStoredResponse:
    try:
        status = sora_service.get_video(video_id)
    except Exception as exc:
        raise _service_error_to_http(exc) from exc

    if status.status != "completed":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Sora video is not completed.",
                "video_id": video_id,
                "status": status.status,
                "progress": status.progress,
                "error": status.error,
            },
        )

    try:
        content = sora_service.download_video_content(video_id)
        safe_user_id, file_path = save_video_content(
            video_id=video_id,
            content=content,
            openwebui_user_id=openwebui_user_id,
        )
    except SoraStorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise _service_error_to_http(exc) from exc

    filename = file_path.name
    return VideoStoredResponse(
        video_id=video_id,
        status="completed",
        stored=True,
        file_path=str(file_path),
        stream_url=build_stream_url(safe_user_id=safe_user_id, filename=filename),
    )


@router.post("/video", response_model=VideoCreateResponse)
def create_sora_video(payload: VideoCreateRequest):
    try:
        created = get_sora_service().create_video(
            prompt=payload.prompt,
            model=payload.model,
            size=payload.size,
            seconds=payload.seconds,
        )
    except Exception as exc:
        raise _service_error_to_http(exc) from exc

    return _response_from_payload(created)


@router.get("/video/{video_id}", response_model=VideoCreateResponse)
def get_sora_video_status(video_id: str):
    try:
        status = get_sora_service().get_video(video_id)
    except Exception as exc:
        raise _service_error_to_http(exc) from exc

    return _response_from_payload(status)


@router.post("/video/{video_id}/download", response_model=VideoStoredResponse)
def download_sora_video(video_id: str, payload: VideoDownloadRequest):
    return _store_completed_video(
        video_id=video_id,
        openwebui_user_id=payload.openwebui_user_id,
        sora_service=get_sora_service(),
    )


@router.post("/video/{video_id}/finalize", response_model=VideoStoredResponse)
def finalize_sora_video(video_id: str, payload: VideoDownloadRequest):
    return _store_completed_video(
        video_id=video_id,
        openwebui_user_id=payload.openwebui_user_id,
        sora_service=get_sora_service(),
    )


@router.get("/video/local/{safe_user_id}/{filename}")
def stream_local_sora_video(safe_user_id: str, filename: str):
    try:
        file_path = get_local_video_path(safe_user_id=safe_user_id, filename=filename)
    except SoraStorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Sora video file not found.")

    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        headers={"Cache-Control": "private, max-age=86400"},
        filename=filename,
        content_disposition_type="inline",
    )
