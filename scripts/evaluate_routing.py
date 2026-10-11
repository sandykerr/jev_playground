#!/usr/bin/env python3
"""Evaluate curated routing tasks; offline by default, --live explicitly calls Jev."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import jev_context as jev
from jev_workers import bounded_map, worker_count

DEFAULT_CASES = Path(__file__).resolve().parents[1] / "evals" / "routing_cases.json"


def load_cases(path, catalog):
    with Path(path).open(encoding="utf-8") as stream:
        raw = stream.read(131073)
    if len(raw) > 131072:
        raise ValueError("evaluation fixture exceeds 128 KiB")
    cases = json.loads(raw)
    if not isinstance(cases, list) or not 1 <= len(cases) <= 128:
        raise ValueError("evaluation requires 1–128 cases")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "task", "require", "must_read", "allowed_read", "workflows"}:
            raise ValueError("invalid evaluation case fields")
        for field in ("id", "task"):
            if not isinstance(case[field], str) or not case[field].strip() or len(case[field]) > 2000:
                raise ValueError("evaluation ID and task must be bounded text")
        if case["id"] in ids:
            raise ValueError("duplicate evaluation case ID")
        ids.add(case["id"])
        for field in ("require", "must_read", "allowed_read", "workflows"):
            if not jev.catalogs.strings(case[field]):
                raise ValueError("evaluation references must be lists of strings")
            known = catalog["workflows"] if field == "workflows" else catalog["documents"]
            if set(case[field]) - set(known):
                raise ValueError(f"unknown evaluation reference in {field}")
        if set(case["must_read"]) - set(case["allowed_read"]):
            raise ValueError("allowed_read must include must_read")
    return cases


def score(case, result):
    documents = {doc["id"]: doc for doc in result["documents"]}
    reads = {key for key, doc in documents.items() if doc["action"] == "read"}
    required = set(case["must_read"])
    return {
        "id": case["id"], "provider": result["provider"], "fallback_reason": result["fallback_reason"],
        "missed_required": sorted(required - reads),
        "false_skips": sorted(key for key in required if documents[key]["requested_action"] == "skip"),
        "missing_files": sorted(key for key, doc in documents.items() if doc["action"] == "missing"),
        "extra_reads": sorted(reads - set(case["allowed_read"])),
        "workflow_misses": sorted(set(case["workflows"]) - set(result["workflows"])),
        "workflow_extras": sorted(set(result["workflows"]) - set(case["workflows"])),
        "read_count": len(reads),
        "inspect_count": sum(doc["action"] == "inspect" for doc in documents.values()),
        "required_count": len(required),
    }


def evaluate_case(job):
    case, root, catalog, live = job
    required = jev.catalogs.pinned_documents(case["task"], case["require"], catalog)
    payload = jev.build_request(case["task"], {}, required, catalog=catalog)
    # Outer case workers own concurrency. Availability checks stay serial inside them.
    local = jev.evaluate(payload, required, offline=True, root=root, catalog=catalog, workers=1)
    result = {"local": score(case, local)}
    if live:
        remote = jev.evaluate(payload, required, root=root, catalog=catalog, workers=1)
        result["jev"] = score(case, remote)
    return result


def summarize(rows):
    fields = ("missed_required", "false_skips", "missing_files", "extra_reads", "workflow_misses", "workflow_extras")
    counts = {field: sum(len(row[field]) for row in rows) for field in fields}
    counts.update(cases=len(rows), jev_responses=sum(row["provider"] == "jev" for row in rows),
                  required_sources=sum(row["required_count"] for row in rows),
                  reads=sum(row["read_count"] for row in rows),
                  inspections=sum(row["inspect_count"] for row in rows))
    counts["required_read_recall"] = (1 - counts["missed_required"] / counts["required_sources"]
                                       if counts["required_sources"] else None)
    counts["passed"] = not any(counts[field] for field in
                               ("missed_required", "false_skips", "missing_files", "workflow_misses", "workflow_extras"))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=jev.ROOT)
    parser.add_argument("--catalog", type=Path, default=jev.catalogs.DEFAULT_CATALOG)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--workers", type=int, help="SLURM_CPUS_PER_TASK or 1; live mode capped at 4 requests")
    parser.add_argument("--live", action="store_true", help="Send curated tasks and catalog metadata to Jev")
    args = parser.parse_args()
    try:
        catalog = jev.catalogs.load_catalog(args.catalog)
        cases = load_cases(args.cases, catalog)
        workers = worker_count(args.workers, len(cases))
        if args.live:
            if not (os.getenv("JEV_API_KEY") or os.getenv("TYPESAFE_API_KEY")):
                raise ValueError("--live requires a configured Jev/TypeSafe key")
            workers = min(workers, 4)  # Bound concurrent external-service requests.
        rows = bounded_map(evaluate_case, [(case, args.repo_root, catalog, args.live) for case in cases], workers)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    modes = ("local", "jev") if args.live else ("local",)
    report = {"schema_version": 1, "workers": workers,
              "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
              "cases_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
              "note": "Curated regression cases, not held-out model-quality or performance evidence. "
                      "Fallback responses do not establish live Jev quality.",
              "results": {mode: {"summary": summarize([row[mode] for row in rows]),
                                 "cases": [row[mode] for row in rows]} for mode in modes}}
    print(json.dumps(report, indent=2))
    return 0 if all(report["results"][mode]["summary"]["passed"] and
                    (mode != "jev" or report["results"][mode]["summary"]["jev_responses"] == len(cases))
                    for mode in modes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
