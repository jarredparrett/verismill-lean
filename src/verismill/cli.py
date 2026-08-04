"""Command line interface for persistent verismill experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .catalog import class_catalog, experiments_root, user_data_root
from .experiment import Experiment
from .schema import AgentRun


def _json(path: str):
    return json.loads(Path(path).read_text())


def cmd_init(args) -> None:
    if args.root is None and not args.id:
        raise SystemExit("init: --id is required when ROOT is omitted")
    root = args.root or experiments_root() / args.id
    exp = Experiment.create(root, request=args.request, experiment_id=args.id)
    print(f"{exp.state['id']}: {exp.root} ({exp.phase.value})")


def cmd_home(args) -> None:
    print(user_data_root())


def cmd_classes(args) -> None:
    value = class_catalog(args.experiments)
    if args.json:
        json.dump(value, sys.stdout, indent=2, sort_keys=True)
        print()
    else:
        print(f"experiment root: {value['experiment_root']}")
        for item in value["classes"]:
            print(f"\n{item['name']}  ({item['era']} · {item['substrate']})")
            print(f"  {item['summary']}")
            standing = item["local_standing"]
            if standing is None:
                print("  local standing: unavailable")
                historical = item["latest_historical_standing"]
                if historical is not None:
                    print(f"  historical evidence: accepted for mattermill "
                          f"{historical['mattermill']} by "
                          f"{historical['experiment_id']} revision "
                          f"{historical['revision']}")
            else:
                print(f"  local standing: accepted by {standing['experiment_id']} "
                      f"revision {standing['revision']} ({standing['scorer']}, "
                      f"k={standing['k']})")
                print(f"  scores: {json.dumps(standing['scores'], sort_keys=True)}")
        for error in value["errors"]:
            print(f"\ninvalid experiment: {error['path']}", file=sys.stderr)
            for failure in error["failures"]:
                print(f"  {failure}", file=sys.stderr)
    if args.strict and value["errors"]:
        raise SystemExit(1)


def cmd_status(args) -> None:
    value = Experiment.open(args.root).view(args.role)
    if args.json:
        json.dump(value, sys.stdout, indent=2, sort_keys=True)
        print()
        return
    print(f"{value['id']} revision {value['revision']}: {value['phase']}")
    print(f"  {value['request']}")
    measurement = value.get("measurement")
    if measurement:
        print(f"  blind measurement: {measurement['status']}")
    for action in value.get("next_actions", []):
        print(f"  next: {action}")


def cmd_prepare(args) -> None:
    exp = Experiment.open(args.root)
    exp.freeze_preparation(research=_json(args.research), rubric=_json(args.rubric),
                           requirements=_json(args.requirements))
    print(f"{exp.state['id']}: rubric frozen")


def cmd_source(args) -> None:
    exp = Experiment.open(args.root)
    ref = exp.source_local_reference(args.file, name=args.name)
    print(ref)


def cmd_agent_run(args) -> None:
    exp = Experiment.open(args.root)
    ref = exp.record_agent_run(AgentRun.from_dict(_json(args.file)))
    print(ref)


def cmd_candidate(args) -> None:
    exp = Experiment.open(args.root)
    ref = exp.record_candidate(artifact=Path(args.artifact).read_bytes(),
                               manifest=_json(args.manifest),
                               builder_run=args.builder_run,
                               explanation=_json(args.explanation))
    print(ref)


def cmd_emit(args) -> None:
    exp = Experiment.open(args.root)
    ref = exp.emit_candidate(
        args.cls, builder_run=args.builder_run,
        explanation=_json(args.explanation), seed=args.seed,
        pins=_json(args.pins) if args.pins else None,
        canon=_json(args.canon) if args.canon else None,
        defect=_json(args.defect) if args.defect else None,
        metadata=_json(args.metadata) if args.metadata else None)
    print(ref)


def cmd_development(args) -> None:
    exp = Experiment.open(args.root)
    ref = exp.record_development_round(candidate=args.candidate,
                                       judge_runs=args.judge_run,
                                       findings=_json(args.findings),
                                       decision=args.decision,
                                       score=_json(args.score))
    print(ref)
    if args.decision == "select":
        print(f"{exp.state['id']}: selected candidate sealed; blind panel required")


def cmd_tell(args) -> None:
    exp = Experiment.open(args.root)
    bbox = [float(item) for item in args.bbox.split(",")] if args.bbox else None
    if bbox is not None and len(bbox) != 4:
        raise SystemExit("tell: --bbox expects x0,y0,x1,y1")
    if bbox is not None and args.page is None:
        raise SystemExit("tell: --bbox requires --page")
    tell = exp.record_tell(tell_class=args.tell_class, path=args.path,
                           rationale=args.rationale, trial_id=args.trial_id,
                           round_no=args.round, quote=args.quote,
                           page=args.page, bbox_norm=bbox)
    json.dump(tell, sys.stdout, indent=2, sort_keys=True)
    print()


def cmd_submit(args) -> None:
    exp = Experiment.open(args.root)
    exp.submit_for_blind_judgment(args.candidate)
    print(f"{exp.state['id']}: awaiting blind judgment")


def cmd_repair(args) -> None:
    exp = Experiment.open(args.root)
    tell = exp.assert_repair(tell_class=args.tell_class, round_no=args.round,
                             quote=args.quote, path=args.path, page=args.page)
    print(json.dumps(tell, sort_keys=True))


def cmd_resolve_repair(args) -> None:
    exp = Experiment.open(args.root)
    tell = exp.resolve_repair(evaluation=args.evaluation,
                              tell_class=args.tell_class, quote=args.quote,
                              path=args.path, page=args.page)
    print(json.dumps(tell, sort_keys=True))


def cmd_judge(args) -> None:
    exp = Experiment.open(args.root)
    if args.mode == "absolute":
        if args.keys:
            raise SystemExit("judge: --keys is only valid with --mode pairwise")
        ref = exp.record_absolute_blind_evaluation(
            judge_runs=args.judge_run, assigned_lenses=args.lens)
    else:
        if not args.keys:
            raise SystemExit("judge: --mode pairwise requires --keys")
        if args.lens:
            raise SystemExit("judge: --lens is only valid with --mode absolute")
        ref = exp.record_pairwise_blind_evaluation(
            keys=_json(args.keys), judge_runs=args.judge_run)
    print(ref)


def cmd_continue(args) -> None:
    exp = Experiment.open(args.root)
    exp.continue_climb()
    print(f"{exp.state['id']}: climbing")


def cmd_report(args) -> None:
    exp = Experiment.open(args.root)
    path = exp.write_report(args.out)
    print(path)


def cmd_verify(args) -> None:
    result = Experiment.open(args.root).verify()
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print()
    if not result["ok"]:
        raise SystemExit(1)


def cmd_replay(args) -> None:
    events = Experiment.open(args.root).replay()
    json.dump(events, sys.stdout, indent=2, sort_keys=True)
    print()


def cmd_rerun(args) -> None:
    child = Experiment.open(args.root).rerun(args.destination,
                                             from_phase=args.from_phase)
    print(f"{child.state['id']}: {child.root} ({child.phase.value})")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="verismill", description=__doc__)
    ap.add_argument("--version", action="version", version=f"verismill {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create an experiment")
    p.add_argument("root", type=Path, nargs="?",
                   help="defaults to the per-user experiment root plus --id")
    p.add_argument("--request", required=True)
    p.add_argument("--id")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("home", help="show the per-user verismill data root")
    p.set_defaults(func=cmd_home)

    p = sub.add_parser(
        "classes", help="merge static capabilities with local verified standing")
    p.add_argument("--experiments", type=Path,
                   help="experiment root; defaults to the per-user data root")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true",
                   help="fail when any discovered experiment is invalid")
    p.set_defaults(func=cmd_classes)

    p = sub.add_parser("status", help="show resumable state")
    p.add_argument("root", type=Path)
    p.add_argument("--role", default="user",
                   choices=("user", "researcher", "builder", "fixer",
                            "development_judge", "blind_judge", "auditor"))
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("prepare", help="freeze research, requirements, and rubric")
    p.add_argument("root", type=Path)
    p.add_argument("--research", required=True)
    p.add_argument("--rubric", required=True)
    p.add_argument("--requirements", required=True)
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("source", help="source a local reference into preparation")
    p.add_argument("root", type=Path)
    p.add_argument("--name", required=True)
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_source)

    p = sub.add_parser("agent-run", help="register a provider-neutral agent receipt")
    p.add_argument("root", type=Path)
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_agent_run)

    p = sub.add_parser("candidate", help="record a generated candidate")
    p.add_argument("root", type=Path)
    p.add_argument("--artifact", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--builder-run", required=True)
    p.add_argument("--explanation", required=True)
    p.set_defaults(func=cmd_candidate)

    p = sub.add_parser("emit", help="render and record a mattermill candidate")
    p.add_argument("root", type=Path)
    p.add_argument("--class", dest="cls", required=True)
    p.add_argument("--builder-run", required=True)
    p.add_argument("--explanation", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--pins")
    p.add_argument("--canon")
    p.add_argument("--defect")
    p.add_argument("--metadata")
    p.set_defaults(func=cmd_emit)

    p = sub.add_parser("development", help="record a development hill-climb round")
    p.add_argument("root", type=Path)
    p.add_argument("--candidate", required=True)
    p.add_argument("--judge-run", action="append", required=True)
    p.add_argument("--findings", required=True)
    p.add_argument("--score", required=True)
    p.add_argument("--decision", choices=("select", "reject", "continue"), required=True)
    p.set_defaults(func=cmd_development)

    p = sub.add_parser("tell", help="record quoted or image-region evidence")
    p.add_argument("root", type=Path)
    p.add_argument("--class", dest="tell_class", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--rationale", required=True)
    p.add_argument("--trial-id", required=True)
    p.add_argument("--round", type=int, required=True)
    locus = p.add_mutually_exclusive_group(required=True)
    locus.add_argument("--quote")
    locus.add_argument("--bbox", help="normalized x0,y0,x1,y1; requires --page")
    p.add_argument("--page", type=int)
    p.set_defaults(func=cmd_tell)

    p = sub.add_parser(
        "submit", help="seal an imported candidate without development selection")
    p.add_argument("root", type=Path)
    p.add_argument("--candidate")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("repair", help="assert a harvested tell repair (unscored)")
    p.add_argument("root", type=Path)
    p.add_argument("--class", dest="tell_class", required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--quote")
    p.add_argument("--path")
    p.add_argument("--page", type=int)
    p.set_defaults(func=cmd_repair)

    p = sub.add_parser(
        "resolve-repair", help="confirm an asserted repair against a blind evaluation")
    p.add_argument("root", type=Path)
    p.add_argument("--evaluation", required=True)
    p.add_argument("--class", dest="tell_class", required=True)
    locus = p.add_mutually_exclusive_group(required=True)
    locus.add_argument("--quote")
    locus.add_argument("--page", type=int)
    p.add_argument("--path")
    p.set_defaults(func=cmd_resolve_repair)

    p = sub.add_parser(
        "judge", help="score recorded blind receipts with a trusted scorer")
    p.add_argument("root", type=Path)
    p.add_argument("--judge-run", action="append", required=True)
    p.add_argument("--mode", choices=("absolute", "pairwise"),
                   default="absolute")
    p.add_argument("--lens", action="append",
                   choices=("arithmetic_and_dates", "procedural_and_citations",
                            "forensic_and_visual"),
                   help="absolute mode; defaults to deterministic lens rotation")
    p.add_argument("--keys", help="pairwise mode: hidden trial-key JSON")
    p.set_defaults(func=cmd_judge)

    p = sub.add_parser("continue", help="continue climbing after a failed judgment")
    p.add_argument("root", type=Path)
    p.set_defaults(func=cmd_continue)

    p = sub.add_parser("report", help="write the human-readable causal report")
    p.add_argument("root", type=Path)
    p.add_argument("--out")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("verify", help="verify object hashes, standing, and bus chain")
    p.add_argument("root", type=Path)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("replay", help="replay recorded events without invoking agents")
    p.add_argument("root", type=Path)
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("rerun", help="create a new development or evaluation attempt")
    p.add_argument("root", type=Path)
    p.add_argument("destination", type=Path)
    p.add_argument("--from", dest="from_phase", choices=("development", "evaluation"),
                   default="development")
    p.set_defaults(func=cmd_rerun)

    return ap


def main() -> int:
    args = parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
