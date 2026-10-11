"""Move legacy Jev private state without overwriting recovery evidence."""
from pathlib import Path


def migrate_context(root):
    """Run before connecting, with old launchers stopped.

    Publication is serial: preflight every collision before moving anything.
    Rename preserves file bytes and permissions; unrelated context stays put.
    """
    root = Path(root)
    legacy = root / "context"
    destination = root / "jev_routing" / "context"
    moves = []
    directories = []

    def plan(source, target):
        if source.is_symlink() or target.is_symlink():
            raise ValueError("Jev context migration refuses symlinks")
        if not target.exists():
            moves.append((source, target))
        elif source.is_dir() and target.is_dir():
            for child in sorted(source.iterdir()):
                plan(child, target / child.name)
            directories.append(source)
        else:
            raise ValueError(f"Jev context migration collision: {target}; retain both copies and resolve before resuming")

    if legacy.is_symlink() or destination.is_symlink():
        raise ValueError("Jev context migration refuses symlinks")
    for name in ("jev-router", "jev-handoffs"):
        source = legacy / name
        if source.exists() or source.is_symlink():
            plan(source, destination / name)
    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        source.rename(target)
    for directory in directories:
        directory.rmdir()
    if legacy.is_dir() and not any(legacy.iterdir()):
        legacy.rmdir()


def relocated_handoff(path, root):
    """Resolve a migrated live registration; historical snapshots stay exact."""
    path, root = Path(path), Path(root)
    try:
        relative = path.relative_to(root / "context" / "jev-handoffs")
    except ValueError:
        return path
    target = root / "jev_routing" / "context" / "jev-handoffs" / relative
    return target if not path.exists() and target.is_file() else path
