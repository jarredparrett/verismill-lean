"""mattermill CLI — emit and inspect deterministic document classes.

Document classes — the things a person asks for by name:

    python -m mattermill.cli classes                   # static capabilities
    python -m mattermill.cli emit --class bill_of_sale --seed 1642 \
        --out bill.pdf --pin vessel_name=Hopewell --pin share=8

`emit` writes the artifact and a sidecar `<out>.manifest.json` — the
reproduction recipe. Same class, version, pins and seed produce the same
bytes, offline, on any machine.

Inspection — read back what the forge emitted:

    python -m mattermill.cli lens --file letter.pdf

`emit` accepts --seed; same arguments produce byte-identical artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, lens, registry

def cmd_classes(args) -> None:
    """The static document-class catalog."""
    classes = registry.list_classes()
    if args.json:
        json.dump(classes, sys.stdout, indent=2)
        print()
        return
    for c in classes:
        print(f"\n{c['name']}  ({c['era']} · {c['substrate']})")
        print(f"  {c['summary']}")
        if c["pins"]:
            print(f"  pins: {', '.join(sorted(c['pins']))}")


def _parse_pin(spec: str):
    """`k=v` with v coerced the way a caller means it: 8 is an int, 0.78 is a
    float, true is a bool, everything else is a string.

    The float case matters as soon as a class takes a ratio — acord130's
    gasoline-receipts share decides the classification, and a string reaching
    the comparison raises a TypeError from deep inside the sampler rather than
    doing what the caller plainly meant."""
    key, _, raw = spec.partition("=")
    if not _:
        raise SystemExit(f"emit: --pin expects key=value, got {spec!r}")
    low = raw.lower()
    if low in ("true", "false"):
        return key, low == "true"
    for cast in (int, float):
        try:
            return key, cast(raw)
        except ValueError:
            continue
    return key, raw


def cmd_emit(args) -> None:
    pins = dict(_parse_pin(p) for p in (args.pin or []))
    canon = json.loads(Path(args.canon).read_text()) if args.canon else None
    defect = json.loads(args.defect) if args.defect else None
    try:
        data, manifest = registry.emit(args.cls, pins=pins or None,
                                       seed=args.seed, canon=canon,
                                       defect=defect)
    except KeyError as e:
        raise SystemExit(str(e).strip('"')) from None

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    manifest["artifact"] = out.name
    Path(str(out) + ".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"{args.cls}: {out} ({len(data)} bytes, seed={args.seed})")
    print(f"  manifest: {out}.manifest.json")


def cmd_lens(args) -> None:
    path = Path(args.file)
    if path.suffix.lower() != ".pdf":
        raise SystemExit(f"lens: expected a .pdf, got {path.suffix!r}")
    info = lens.pdf_info(path)
    json.dump(info, sys.stdout, indent=2, sort_keys=True)
    print()


def main() -> int:
    ap = argparse.ArgumentParser(prog="mattermill", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"mattermill {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("classes", help="list static document-class capabilities")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_classes)

    p = sub.add_parser("emit", help="render one document of a class")
    p.add_argument("--class", dest="cls", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--pin", action="append", metavar="KEY=VALUE",
                   help="pin a fact the caller owns; repeatable")
    p.add_argument("--canon", metavar="FILE.json",
                   help="caller-supplied world facts for canon-driven classes")
    p.add_argument("--defect", metavar="JSON",
                   help='plant one fault, e.g. \'{"regnal_year": "fifteenth"}\'')
    p.set_defaults(fn=cmd_emit)


    p = sub.add_parser("lens")
    p.add_argument("--file", required=True)
    p.set_defaults(fn=cmd_lens)

    args = ap.parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
