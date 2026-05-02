from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.responses import FileResponse

from api.routes import video_router
from api.services.sora_service import SoraVideoPayload


@dataclass
class FakeSoraService:
    status: str = "completed"
    progress: int | None = 100
    content: bytes = b"fake-mp4"

    def create_video(self, *, prompt, model, size, seconds):
        return SoraVideoPayload(
            id="video_abc123",
            status="queued",
            model=model,
            progress=0,
            size=size,
            seconds=str(seconds),
        )

    def get_video(self, video_id: str):
        return SoraVideoPayload(
            id=video_id,
            status=self.status,
            model="sora-2",
            progress=self.progress,
            size="1280x720",
            seconds="8",
        )

    def download_video_content(self, video_id: str):
        return self.content


class VideoRouterTests(unittest.TestCase):
    def test_create_returns_sora_job_metadata(self):
        with patch.object(video_router, "get_sora_service", return_value=FakeSoraService()):
            response = video_router.create_sora_video(
                video_router.VideoCreateRequest(
                    prompt="A golden retriever runs through leaves",
                    model="sora-2",
                    size="1280x720",
                    seconds=8,
                    openwebui_user_id="jmnovak",
                )
            )

        data = response.model_dump()
        self.assertEqual(data["id"], "video_abc123")
        self.assertEqual(data["seconds"], "8")
        self.assertEqual(data["status"], "queued")

    def test_create_validation_errors_return_400(self):
        with self.assertRaises(HTTPException) as raised:
            video_router.create_sora_video(
                video_router.VideoCreateRequest(
                    prompt="A prompt",
                    model="sora-2",
                    size="1920x1080",
                    seconds="8",
                )
            )

        self.assertEqual(raised.exception.status_code, 400)

    def test_poll_returns_status(self):
        with patch.object(
            video_router,
            "get_sora_service",
            return_value=FakeSoraService(status="in_progress", progress=33),
        ):
            response = video_router.get_sora_video_status("video_abc123")

        data = response.model_dump()
        self.assertEqual(data["status"], "in_progress")
        self.assertEqual(data["progress"], 33)

    def test_download_returns_409_before_completion(self):
        with patch.object(
            video_router,
            "get_sora_service",
            return_value=FakeSoraService(status="in_progress", progress=50),
        ):
            with self.assertRaises(HTTPException) as raised:
                video_router.download_sora_video(
                    "video_abc123",
                    video_router.VideoDownloadRequest(openwebui_user_id="jmnovak"),
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["status"], "in_progress")

    def test_download_stores_completed_video_and_streams_mp4(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"SORA_STORAGE_ROOT": tmpdir}, clear=False):
                with patch.object(video_router, "get_sora_service", return_value=FakeSoraService()):
                    download_response = video_router.download_sora_video(
                        "video_abc123",
                        video_router.VideoDownloadRequest(openwebui_user_id="JMNovak@example.com"),
                    )

                data = download_response.model_dump()
                self.assertTrue(data["stored"])
                self.assertEqual(
                    data["stream_url"],
                    "/api/agent/video/local/jmnovak_example_com/video_abc123.mp4",
                )
                self.assertEqual(Path(data["file_path"]).read_bytes(), b"fake-mp4")

                stream_response = video_router.stream_local_sora_video(
                    "jmnovak_example_com",
                    "video_abc123.mp4",
                )

        self.assertIsInstance(stream_response, FileResponse)
        self.assertEqual(stream_response.media_type, "video/mp4")
        self.assertEqual(stream_response.headers["cache-control"], "private, max-age=86400")
        self.assertIn("inline", stream_response.headers["content-disposition"])

    def test_local_stream_rejects_non_mp4_filename(self):
        with self.assertRaises(HTTPException) as raised:
            video_router.stream_local_sora_video("jmnovak", "video.txt")

        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
