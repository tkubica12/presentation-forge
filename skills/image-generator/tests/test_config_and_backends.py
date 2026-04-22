from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from image_generator.backends import _normalize_gpt_size
from image_generator.config import JobConfig


class NormalizeGptSizeTests(unittest.TestCase):
    def test_gpt_image_2_preserves_supported_custom_square_size(self) -> None:
        self.assertEqual(_normalize_gpt_size("2048x2048", "gpt-image-2"), "2048x2048")

    def test_gpt_image_2_preserves_supported_custom_16_9_size(self) -> None:
        self.assertEqual(_normalize_gpt_size("3840x2160", "gpt-image-2"), "3840x2160")

    def test_legacy_gpt_snaps_to_old_size_tiers(self) -> None:
        self.assertEqual(_normalize_gpt_size("2048x2048", "gpt-image-1.5"), "1024x1024")
        self.assertEqual(_normalize_gpt_size("3840x2160", "gpt-image-1.5"), "1536x1024")


class ConfigInputImageTests(unittest.TestCase):
    def test_relative_input_images_resolve_from_yaml_folder(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            assets = folder / "assets"
            assets.mkdir()
            (assets / "logo.jpg").write_bytes(b"jpg")
            (assets / "global.jpg").write_bytes(b"jpg")
            yaml_path = folder / "job.yaml"
            yaml_path.write_text(
                textwrap.dedent(
                    """
                    common_requirements: test
                    input_image: ./assets/global.jpg
                    images:
                      - name: one
                        description: one
                      - name: two
                        description: two
                        input_image: ./assets/logo.jpg
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            cfg = JobConfig.from_yaml(yaml_path)

            self.assertEqual(cfg.input_image, str((assets / "global.jpg").resolve()))
            self.assertIsNone(cfg.images[0].input_image)
            self.assertEqual(cfg.images[1].input_image, str((assets / "logo.jpg").resolve()))


if __name__ == "__main__":
    unittest.main()
