"""Native template sourcing — reference forms in, template contracts out.

The acord 0.2.0 rebuild proved the lesson this module encodes: the reference
artifact is the load-bearing input. A from-memory layout of a standard form
reads as directionally correct and fails under a real look (wrong section
inventory, wrong edition, invented blocks). So sourcing is first-class:

    fetch/register -> provenance -> contract -> proposed markers -> emitter

Layout on disk (per template, under .foundry/reference/<name>/):

    source.pdf        the reference form
    provenance.json   url or local origin, sha256, bytes, retrieval date
    contract.json     per-page extracted text lines + proposed markers

The contract is the derived artifact emitters and capability tests build
against; the toolsmith curates PAGE_MARKERS from its proposals.

Authoring-time only, and the one module here that touches the network. The
render path never imports it (invariant 5) — a sourced form is bytes on disk
by the time an emitter sees it.

The `%PDF` check is not a formality. A landing page saved under a `.pdf` name
is the standard failure of this step, and it is silent: the file exists, the
name is right, and the extraction downstream just finds no form.

Run:

    PYTHONPATH=src .venv/bin/python -m verismill.source \
        --name acord125 --url https://example.com/acord-125.pdf
    PYTHONPATH=src .venv/bin/python -m verismill.source \
        --name acord126 --file "~/Downloads/Acord126 GL.pdf"
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

DEFAULT_OUT = Path(".foundry/reference")

_FORM_MARK = re.compile(r"[A-Z]+ \d+ \(\d{4}/\d{2}\)")
_PAGE_MARK = re.compile(r"Page \d+ of \d+")
_SECTION = re.compile(r"^[0-9A-Z][0-9A-Z &/,'#().:%$-]{2,70}$")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, name: str, out_root: Path = DEFAULT_OUT, timeout: int = 60) -> Path:
    """Download a reference form, verify it is a PDF, record provenance."""
    req = urllib.request.Request(url, headers={"User-Agent": "verismill-template-sourcer/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return _register(data, name, out_root, origin={"url": url})


def register_local(path: str | Path, name: str, out_root: Path = DEFAULT_OUT) -> Path:
    """Register an operator-supplied reference form (no network)."""
    src = Path(path).expanduser()
    return _register(src.read_bytes(), name, out_root,
                     origin={"local_path": str(src)})


def _register(data: bytes, name: str, out_root: Path, origin: dict) -> Path:
    if not data.startswith(b"%PDF"):
        raise ValueError(f"{name}: not a PDF (starts {data[:8]!r})")
    dest = out_root / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "source.pdf").write_bytes(data)
    (dest / "provenance.json").write_text(json.dumps({
        "name": name, **origin, "sha256": _sha256(data), "bytes": len(data),
        "retrieved_utc": _dt.datetime.now(_dt.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2) + "\n")
    return dest / "source.pdf"


def extract_contract(pdf_path: str | Path) -> dict:
    """Per-page text extraction. pypdfium2 is an authoring-time dependency —
    a clear error here must never become a render-path runtime error."""
    try:
        import pypdfium2 as pdfium
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "template extraction needs pypdfium2 (authoring-time dep): "
            "pip install pypdfium2") from e
    doc = pdfium.PdfDocument(str(pdf_path))
    pages = []
    size = None
    for page in doc:
        size = size or list(page.get_size())
        text = page.get_textpage().get_text_bounded()
        pages.append([ln.strip() for ln in text.splitlines() if ln.strip()])
    return {"pages": len(pages), "page_size": size, "page_lines": pages}


def propose_markers(contract: dict, per_page: int = 24) -> dict[str, list[str]]:
    """Heuristic marker proposal for the emitter's capability test: form-number
    and pagination marks always; then caps-style section/label lines, longest
    first (longer strings are less likely to collide in a content stream).
    The toolsmith curates from these — proposal, not verdict."""
    out: dict[str, list[str]] = {}
    for i, lines in enumerate(contract["page_lines"], 1):
        picked, seen = [], set()
        for ln in lines:
            # form-number / pagination marks are proposed as the matched
            # substring — extraction can merge same-baseline footer runs
            for rx in (_FORM_MARK, _PAGE_MARK):
                m = rx.search(ln)
                if m and m.group(0) not in seen:
                    seen.add(m.group(0))
                    picked.append(m.group(0))
        caps = [ln for ln in lines
                if ln not in seen and _SECTION.match(ln)
                and any(c.isalpha() for c in ln) and ln.upper() == ln]
        for ln in sorted(caps, key=len, reverse=True)[:per_page - len(picked)]:
            seen.add(ln)
            picked.append(ln)
        out[str(i)] = picked
    return out


def write_contract(name: str, out_root: Path = DEFAULT_OUT) -> Path:
    dest = out_root / name
    contract = extract_contract(dest / "source.pdf")
    contract["proposed_markers"] = propose_markers(contract)
    contract["provenance"] = json.loads((dest / "provenance.json").read_text())
    path = dest / "contract.json"
    path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", required=True, help="template slug, e.g. acord125")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="fetch the reference form from this URL")
    src.add_argument("--file", help="register an operator-supplied local PDF")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    if args.url:
        pdf = fetch(args.url, args.name, args.out)
    else:
        pdf = register_local(args.file, args.name, args.out)
    contract = write_contract(args.name, args.out)
    meta = json.loads(contract.read_text())
    print(f"{args.name}: {meta['pages']} pages, contract -> {contract}")
    for page, markers in meta["proposed_markers"].items():
        print(f"  p{page}: {len(markers)} markers, e.g. {markers[:3]}")


if __name__ == "__main__":
    main()
