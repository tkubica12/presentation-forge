"""Tests for template_utils.normalize_template_to_pptx."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from presentation_forge.template_utils import (
    POTX_CONTENT_TYPE,
    PPTX_CONTENT_TYPE,
    normalize_template_to_pptx,
)


def _build_fake_potx(path: Path, *, content_type: bytes = POTX_CONTENT_TYPE) -> None:
    """Build a stub OOXML zip with a Content_Types entry only."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            b'<?xml version="1.0"?><Types><Default ContentType="'
            + content_type
            + b'"/></Types>',
        )
        z.writestr("ppt/presentation.xml", b"<?xml version='1.0'?><p/>")
    path.write_bytes(buf.getvalue())


def test_potx_to_pptx_rewrites_content_type(tmp_path):
    src = tmp_path / "in.potx"
    dst = tmp_path / "out.pptx"
    _build_fake_potx(src)

    out = normalize_template_to_pptx(src, dst)

    assert out == dst
    assert dst.exists()
    with zipfile.ZipFile(dst) as z:
        ct = z.read("[Content_Types].xml")
    assert PPTX_CONTENT_TYPE in ct
    assert POTX_CONTENT_TYPE not in ct


def test_pptx_input_is_copied_verbatim(tmp_path):
    src = tmp_path / "in.pptx"
    dst = tmp_path / "out.pptx"
    _build_fake_potx(src, content_type=PPTX_CONTENT_TYPE)
    src_bytes = src.read_bytes()

    out = normalize_template_to_pptx(src, dst)

    assert out == dst
    assert dst.read_bytes() == src_bytes


def test_unknown_extension_is_rejected(tmp_path):
    src = tmp_path / "in.ppt"
    src.write_bytes(b"\x00\x00")
    with pytest.raises(ValueError, match="unsupported template extension"):
        normalize_template_to_pptx(src, tmp_path / "out.pptx")


def test_missing_template_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        normalize_template_to_pptx(tmp_path / "nope.potx", tmp_path / "out.pptx")


def test_dest_parent_is_created(tmp_path):
    src = tmp_path / "in.potx"
    _build_fake_potx(src)
    deep_dst = tmp_path / "a" / "b" / "c" / "out.pptx"
    out = normalize_template_to_pptx(src, deep_dst)
    assert out.exists()
    assert out.parent.is_dir()


def test_real_microsoft_template_round_trips(microsoft_template_path, tmp_path):
    """The user's real .potx must open in python-pptx after normalization."""
    pptx = tmp_path / "ms.pptx"
    normalize_template_to_pptx(microsoft_template_path, pptx)
    from pptx import Presentation

    prs = Presentation(str(pptx))
    layout_names = {layout.name for layout in prs.slide_layouts}
    for required in ("Title Slide 1", "Title and Content", "Quote"):
        assert required in layout_names, f"layout {required!r} missing"
