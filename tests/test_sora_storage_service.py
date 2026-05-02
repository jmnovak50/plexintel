from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from api.scripts.cleanup_sora_files import cleanup_sora_files
from api.services.sora_storage_service import (
    SoraStorageError,
    get_local_video_path,
    sanitize_openwebui_user_id,
    save_video_content,
)


class SoraStorageServiceTests(unittest.TestCase):
    def test_sanitize_user_id_is_stable_and_path_safe(self):
        self.assertEqual(sanitize_openwebui_user_id("JMNovak@example.com"), "jmnovak_example_com")
        self.assertEqual(sanitize_openwebui_user_id("../../Root"), "root")
        self.assertEqual(sanitize_openwebui_user_id(""), "unknown_user")

    def test_save_video_content_writes_under_configured_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"SORA_STORAGE_ROOT": tmpdir}, clear=False):
                safe_user_id, path = save_video_content(
                    video_id="video_abc123",
                    content=b"mp4-bytes",
                    openwebui_user_id="JMNovak@example.com",
                )

                self.assertEqual(safe_user_id, "jmnovak_example_com")
                self.assertEqual(path.read_bytes(), b"mp4-bytes")
                self.assertEqual(path.name, "video_abc123.mp4")
                self.assertTrue(str(path).startswith(str(Path(tmpdir).resolve())))

    def test_local_video_path_rejects_unsafe_inputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"SORA_STORAGE_ROOT": tmpdir}, clear=False):
                with self.assertRaises(SoraStorageError):
                    get_local_video_path(safe_user_id="../user", filename="video.mp4")
                with self.assertRaises(SoraStorageError):
                    get_local_video_path(safe_user_id="jmnovak", filename="../video.mp4")
                with self.assertRaises(SoraStorageError):
                    get_local_video_path(safe_user_id="jmnovak", filename="video.txt")

    def test_cleanup_deletes_old_files_and_preserves_fresh_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            user_dir = root / "jmnovak"
            old_empty_dir = root / "empty_user"
            user_dir.mkdir()
            old_empty_dir.mkdir()
            old_file = user_dir / "old.mp4"
            fresh_file = user_dir / "fresh.mp4"
            old_file.write_bytes(b"old")
            fresh_file.write_bytes(b"fresh")
            old_time = time.time() - (25 * 3600)
            os.utime(old_file, (old_time, old_time))

            with patch.dict(
                os.environ,
                {"SORA_STORAGE_ROOT": tmpdir, "SORA_RETENTION_HOURS": "24"},
                clear=False,
            ):
                deleted_count = cleanup_sora_files()

            self.assertEqual(deleted_count, 1)
            self.assertFalse(old_file.exists())
            self.assertTrue(fresh_file.exists())
            self.assertFalse(old_empty_dir.exists())


if __name__ == "__main__":
    unittest.main()
