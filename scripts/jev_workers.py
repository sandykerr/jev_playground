"""Bounded spawn workers for independent metadata and evaluation jobs."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import os


def worker_count(override=None, jobs=1):
    value = override if override is not None else os.environ.get("SLURM_CPUS_PER_TASK", "1")
    try:
        count = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("workers / SLURM_CPUS_PER_TASK must be a positive integer") from error
    if count < 1:
        raise ValueError("workers must be positive")
    return min(count, max(1, jobs))


def bounded_map(function, jobs, workers=None):
    """Ordered results; at most two queued jobs per worker; no pool in serial mode."""
    count = worker_count(workers, len(jobs))
    if count == 1:
        return [function(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=count, mp_context=multiprocessing.get_context("spawn")) as pool:
        remaining = iter(jobs)
        pending = deque()
        for _ in range(min(len(jobs), 2 * count)):
            pending.append(pool.submit(function, next(remaining)))
        results = []
        exhausted = object()
        while pending:
            results.append(pending.popleft().result())
            job = next(remaining, exhausted)
            if job is not exhausted:
                pending.append(pool.submit(function, job))
    return results
