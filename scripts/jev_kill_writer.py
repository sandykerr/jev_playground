#!/usr/bin/env python3
"""Stop one Linux Codex thread writer, identified by its native kernel lock."""
import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import select
import signal
import stat
import sys

from jev_workers import bounded_map, worker_count

THREAD_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


class WriterError(RuntimeError):
    pass


def file_identity(path):
    """Worker-local metadata only; never read session bodies or lock contents."""
    path = Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise WriterError(f"Not a regular lock file: {path}")
    return path.stem, (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)


def parse_locks(text):
    locks = []
    for line in text.splitlines():
        fields = line.split()
        # Blocked waiters are not holders; OFD locks have no identifiable PID.
        if len(fields) < 8 or fields[1] == "->" or fields[3] != "WRITE":
            continue
        try:
            major, minor, inode = fields[5].split(":")
            locks.append((int(fields[4]), (int(major, 16), int(minor, 16), int(inode))))
        except ValueError as error:
            raise WriterError("Unrecognized /proc/locks record; refusing to guess") from error
    return locks


def process_identity(pid, proc_root=Path('/proc')):
    directory = Path(proc_root) / str(pid)
    if directory.stat().st_uid != os.getuid():
        raise WriterError("Writer belongs to another user")
    raw = (directory / 'stat').read_text()
    fields = raw[raw.rfind(')') + 2:].split()
    # Fields 4 and 22, after PID and parenthesized command (which may contain spaces).
    ppid, started = int(fields[1]), int(fields[19])
    args = (directory / 'cmdline').read_bytes().split(b'\0')
    argv = [os.fsdecode(arg) for arg in args if arg]
    executable = Path(os.readlink(directory / 'exe')).name
    if executable not in ('codex', 'codex.exe') or 'app-server' not in argv[1:]:
        raise WriterError("Lock owner is not a recognizable Codex App Server; refusing to signal it")
    if pid in (os.getpid(), os.getppid()) or pid <= 1:
        raise WriterError("Refusing to stop this command or its parent")
    return ppid, started


@dataclass(frozen=True)
class Writer:
    thread_id: str
    pid: int
    ppid: int
    started: int
    inode: tuple
    threads: tuple = ()


def inspect_writer(thread_id, codex_home, workers=None, proc_root=Path('/proc'),
                   also_stop=(), inspect_only=False):
    if not THREAD_ID.fullmatch(thread_id) or any(not THREAD_ID.fullmatch(t) for t in also_stop):
        raise WriterError("Invalid thread ID")
    lock_dir = Path(codex_home) / 'thread-writer-locks'
    if lock_dir.is_symlink():
        raise WriterError("Refusing a symlinked writer-lock directory")
    target = file_identity(lock_dir / f'{thread_id}.lock')
    if target is None:
        raise WriterError("No native lock file for this thread. It may be inactive, or use another Codex home/version.")
    locks = parse_locks((Path(proc_root) / 'locks').read_text())
    holders = {pid for pid, inode in locks if inode == target[1]}
    if len(holders) != 1 or next(iter(holders)) <= 0:
        raise WriterError("No unique visible writer PID. Run on the host, outside a PID sandbox; no process was selected.")
    pid = next(iter(holders))
    # Metadata checks are independent. Reconciliation and signaling stay serial.
    paths = sorted(lock_dir.glob('*.lock'))
    entries = bounded_map(file_identity, paths, workers)
    owned = {inode for owner, inode in locks if owner == pid}
    threads = sorted(name for entry in entries if entry is not None
                     for name, inode in [entry] if inode in owned and THREAD_ID.fullmatch(name))
    if thread_id not in threads:
        raise WriterError("Target thread lock changed during inspection; rerun the command")
    if not inspect_only and set(threads) != {thread_id, *also_stop}:
        raise WriterError("Writer owns multiple or changing thread locks; refusing to stop a shared server: "
                          + ', '.join(threads)
                          + ". Use --dry-run to inspect; --also-stop OTHER_THREAD_ID acknowledges each additional thread.")
    ppid, started = process_identity(pid, proc_root)
    return Writer(thread_id, pid, ppid, started, target[1], tuple(threads))


def stop_writer(writer, codex_home, timeout=5, force=False, workers=None, also_stop=()):
    """Use a pidfd to avoid signaling a different process after PID reuse."""
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise WriterError("This Linux/Python installation lacks pidfd support; no signal was sent")
    with_pid = os.pidfd_open(writer.pid)
    try:
        if inspect_writer(writer.thread_id, codex_home, workers, also_stop=also_stop) != writer:
            raise WriterError("Writer identity changed during inspection; rerun the command")
        signal.pidfd_send_signal(with_pid, signal.SIGTERM)
        poller = select.poll()
        poller.register(with_pid, select.POLLIN)
        if poller.poll(math.ceil(timeout * 1000)):
            return 'terminated'
        if not force:
            raise WriterError("SIGTERM sent, but writer has not exited. Inspect it or rerun with --force.")
        # Do not escalate against a process that released/reassigned the thread.
        if inspect_writer(writer.thread_id, codex_home, workers, also_stop=also_stop) != writer:
            raise WriterError("Writer ownership changed after SIGTERM; refusing force escalation")
        signal.pidfd_send_signal(with_pid, signal.SIGKILL)
        if not poller.poll(math.ceil(timeout * 1000)):
            raise WriterError("SIGKILL sent, but process exit has not been observed")
        return 'killed'
    finally:
        os.close(with_pid)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('thread_id', help='Exact thread ID to stop')
    parser.add_argument('--codex-home', type=Path,
                        default=Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')))
    parser.add_argument('--dry-run', action='store_true', help='Identify the writer without signaling it')
    parser.add_argument('--also-stop', action='append', default=[], metavar='THREAD_ID',
                        help='Acknowledge another thread interrupted by stopping this shared writer; repeat per thread')
    parser.add_argument('--force', action='store_true', help='Escalate to SIGKILL only if SIGTERM times out')
    parser.add_argument('--timeout', type=float, default=5, help='Seconds to wait per signal, 0–30 (default 5)')
    parser.add_argument('--workers', type=int, help='Lock metadata workers; SLURM_CPUS_PER_TASK or 1')
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 30:
        parser.error('--timeout must be greater than 0 and at most 30 seconds')
    try:
        if sys.platform != 'linux':
            raise WriterError('This command currently supports Linux only')
        worker_count(args.workers)
        writer = inspect_writer(args.thread_id, args.codex_home, args.workers,
                                also_stop=args.also_stop, inspect_only=args.dry_run)
        print(json.dumps({'thread_id': writer.thread_id, 'writer_pid': writer.pid,
                          'parent_pid': writer.ppid, 'affected_threads': writer.threads, 'dry_run': args.dry_run}), flush=True)
        if not args.dry_run:
            result = stop_writer(writer, args.codex_home, args.timeout, args.force, args.workers,
                                 also_stop=args.also_stop)
            print(f'Writer {writer.pid} {result}. Retry your Jev --resume command.')
        return 0
    except (WriterError, OSError, ValueError) as error:
        print(f'Cannot stop writer: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrupted; a signal already sent cannot be undone.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
