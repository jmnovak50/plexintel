from __future__ import annotations

import unittest

from api.services.sora_service import (
    SoraValidationError,
    normalize_sora_model,
    normalize_sora_seconds,
    normalize_sora_size,
)


class SoraServiceValidationTests(unittest.TestCase):
    def test_seconds_accepts_string_enum_and_coerces_ints(self):
        self.assertEqual(normalize_sora_seconds("4"), "4")
        self.assertEqual(normalize_sora_seconds("8"), "8")
        self.assertEqual(normalize_sora_seconds("12"), "12")
        self.assertEqual(normalize_sora_seconds(4), "4")
        self.assertEqual(normalize_sora_seconds(8), "8")
        self.assertEqual(normalize_sora_seconds(12), "12")

    def test_invalid_seconds_raises_validation_error(self):
        with self.assertRaises(SoraValidationError):
            normalize_sora_seconds(6)

    def test_model_validation(self):
        self.assertEqual(normalize_sora_model("sora-2"), "sora-2")
        self.assertEqual(normalize_sora_model("sora-2-pro"), "sora-2-pro")
        with self.assertRaises(SoraValidationError):
            normalize_sora_model("gpt-image-1")

    def test_size_validation_uses_official_openai_values(self):
        for size in ("1280x720", "720x1280", "1024x1792", "1792x1024"):
            self.assertEqual(normalize_sora_size(size), size)

        with self.assertRaises(SoraValidationError):
            normalize_sora_size("1920x1080")


if __name__ == "__main__":
    unittest.main()
