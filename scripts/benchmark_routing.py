#!/usr/bin/env python3
"""HPC-only serial/parallel offline evaluation timings; no model or raster work."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

from jev_workers import worker_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, help="Default SLURM_CPUS_PER_TASK, capped by case count")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if not os.getenv("SLURM_JOB_ID") or not (os.getenv("APPTAINER_CONTAINER") or os.getenv("SINGULARITY_CONTAINER")):
        parser.error("timing requires a Slurm allocation and the project container; use the supplied sbatch wrapper")
    if not 1 <= args.repeats <= 10:
        parser.error("repeats must be between 1 and 10")
    try:
        count = worker_count(args.workers, jobs=128)
    except ValueError as error:
        parser.error(str(error))
    script = Path(__file__).with_name("evaluate_routing.py")
    samples = {1: [], count: []}
    reference = None
    actual_workers = None
    # Sequential trials avoid competing pools/I/O and let each trial own its allocation.
    for repeat in range(args.repeats):
        order = list(samples) if repeat % 2 == 0 else list(reversed(samples))
        for workers in order:
            start = time.perf_counter()
            result = subprocess.run([sys.executable, str(script), "--workers", str(workers)],
                                    capture_output=True, text=True, check=True)
            samples[workers].append(time.perf_counter() - start)
            report = json.loads(result.stdout)
            if workers == count:
                actual_workers = report["workers"]
            if reference is not None and report["results"] != reference["results"]:
                raise RuntimeError("serial/parallel routing reports differ")
            reference = report
    medians = {key: statistics.median(values) for key, values in samples.items()}
    print(json.dumps({"job_id": os.environ["SLURM_JOB_ID"], "requested_workers": count,
                      "effective_workers": actual_workers, "seconds": samples,
                      "median_seconds": medians, "serial_over_parallel": medians[1] / medians[count],
                      "catalog_sha256": reference["catalog_sha256"], "cases_sha256": reference["cases_sha256"],
                      "identical_results": True, "summary": reference["results"]["local"]["summary"],
                      "note": "Ratio >1 means parallel was faster for this small fixture workload only."}, indent=2))


if __name__ == "__main__":
    main()
