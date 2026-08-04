"""The lens: read back what the forge emitted.

One library defines both sides — an emitter renders a feature, the gates and
the capability tests verify it here, and "what counts as a feature" can never
drift between them.

Every registered document class ships as PDF, so the inspection surface is
deliberately PDF-only.
"""

from __future__ import annotations

import re
from pathlib import Path

_META = {
    # PDF string literals: escaped parens allowed inside ((?:\\.|[^()\\])*)
    "producer": re.compile(rb"/Producer\s*\(((?:\\.|[^()\\])*)\)", re.S),
    "creator": re.compile(rb"/Creator\s*\(((?:\\.|[^()\\])*)\)", re.S),
    "created": re.compile(rb"/CreationDate\s*\(((?:\\.|[^()\\])*)\)"),
    "modified": re.compile(rb"/ModDate\s*\(((?:\\.|[^()\\])*)\)"),
    "title": re.compile(rb"/Title\s*\(((?:\\.|[^()\\])*)\)", re.S),
}
_BATES = re.compile(rb"[A-Z][A-Z0-9_]+_?\d{4,6}")
_PAGE = re.compile(rb"/Type\s*/Page[^s]")


def _unescape(s: bytes) -> str:
    return s.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\").decode("latin-1", "replace")


def _flate_streams(raw: bytes) -> bytes:
    """Decompress all streams so content (bates stamps, page text) is
    searchable. Handles plain FlateDecode and reportlab's default
    ASCII85+Flate chain."""
    import base64
    import zlib
    out = bytearray()
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
        data = m.group(1).strip(b"\r\n")
        try:
            out += zlib.decompress(data)
            continue
        except zlib.error:
            pass
        try:
            out += zlib.decompress(base64.a85decode(data, adobe=True))
        except Exception:
            pass
    return bytes(out)


def pdf_info(path: str | Path) -> dict:
    raw = Path(path).read_bytes()
    content = raw + _flate_streams(raw)
    meta = {k: (_unescape(m.group(1)) if (m := rx.search(raw)) else None)
            for k, rx in _META.items()}
    return {
        "pages": len(_PAGE.findall(raw)),
        **meta,
        "bates_stamps": sorted({b.decode() for b in _BATES.findall(content)}),
    }


