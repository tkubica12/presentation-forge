"""PowerPoint template helpers.

`python-pptx` (and therefore the vendored hve-core skill) cannot open
`.potx` files directly — it expects the regular presentation content type
(`application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml`)
rather than the template content type
(`application/vnd.openxmlformats-officedocument.presentationml.template.main+xml`).

This module provides `normalize_template_to_pptx`, which copies the template
into a cache directory and patches `[Content_Types].xml` so that
`python-pptx` accepts it. The function is a no-op for files that are already
`.pptx` (it just copies them).
"""
from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

POTX_CONTENT_TYPE = (
    b"application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"
)
PPTX_CONTENT_TYPE = (
    b"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
)


def normalize_template_to_pptx(template_path: Path, dest_path: Path) -> Path:
    """Copy *template_path* to *dest_path* as a `.pptx` python-pptx can open.

    If the template is already a `.pptx`, the file is copied as-is (a fresh
    copy under `dest_path`). For `.potx`, the central `[Content_Types].xml`
    entry is rewritten so the package advertises itself as a regular
    presentation. Returns the destination path.
    """
    template_path = Path(template_path)
    dest_path = Path(dest_path)
    if not template_path.is_file():
        raise FileNotFoundError(f"template not found: {template_path}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    suffix = template_path.suffix.lower()
    if suffix == ".pptx":
        shutil.copyfile(template_path, dest_path)
        return dest_path
    if suffix != ".potx":
        raise ValueError(
            f"unsupported template extension {suffix!r}; expected .pptx or .potx"
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(template_path, "r") as zin:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "[Content_Types].xml":
                    data = data.replace(POTX_CONTENT_TYPE, PPTX_CONTENT_TYPE)
                zout.writestr(item, data)
    dest_path.write_bytes(buf.getvalue())
    return dest_path
