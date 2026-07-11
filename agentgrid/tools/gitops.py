"""Git operations used by the orchestrator: clones, worktrees, merges.

All identity is pinned so runs work on pristine machines; all commands go
through run_git() which raises with full stderr on failure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..errors import PipelineError

_IDENTITY = ["-c", "user.name=AgentGrid", "-c", "user.email=agents@agentgrid.local",
             "-c", "commit.gpgsign=false"]


def run_git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", *_IDENTITY, *args]
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise PipelineError(
            f"git {' '.join(args)} failed in {cwd}:\n{proc.stdout}\n{proc.stderr}")
    return proc


def init_repo(path: Path) -> None:
    run_git(path, "init", "-b", "main")


def commit_all(repo: Path, message: str) -> bool:
    """Stage everything and commit. Returns False when nothing changed."""
    run_git(repo, "add", "-A")
    status = run_git(repo, "status", "--porcelain").stdout.strip()
    if not status:
        return False
    run_git(repo, "commit", "--no-verify", "-m", message)
    return True


def clone(src: Path, dst: Path) -> None:
    run_git(src.parent if src.parent.exists() else Path("."),
            "clone", "--quiet", str(src), str(dst))


def clone_bare(src: Path, dst: Path) -> None:
    run_git(src.parent, "clone", "--quiet", "--bare", str(src), str(dst))


def add_worktree(repo: Path, wt_dir: Path, branch: str, base: str = "main") -> None:
    run_git(repo, "worktree", "add", "-b", branch, str(wt_dir), base)


def remove_worktree(repo: Path, wt_dir: Path) -> None:
    run_git(repo, "worktree", "remove", "--force", str(wt_dir), check=False)
    run_git(repo, "worktree", "prune", check=False)


def diff(repo: Path, base: str, head: str = "") -> str:
    ref = f"{base}..{head}" if head else base
    return run_git(repo, "diff", ref).stdout


def checkout_new(repo: Path, branch: str, base: str = "main") -> None:
    run_git(repo, "checkout", "-q", "-b", branch, base)


def checkout(repo: Path, branch: str) -> None:
    run_git(repo, "checkout", "-q", branch)


def merge(repo: Path, branch: str, message: str = "") -> tuple[bool, list[str]]:
    """Merge `branch` into the current branch.

    Returns (clean, conflicted_paths). On conflict the merge is left in
    progress so the Integrator agent can resolve and commit.
    """
    msg = message or f"merge {branch}"
    proc = run_git(repo, "merge", "--no-ff", "--no-edit", "-m", msg, branch, check=False)
    if proc.returncode == 0:
        return True, []
    conflicted = run_git(repo, "diff", "--name-only", "--diff-filter=U").stdout.split()
    if not conflicted:
        raise PipelineError(f"merge of {branch} failed without conflicts:\n"
                            f"{proc.stdout}\n{proc.stderr}")
    return False, conflicted


def conclude_merge(repo: Path, message: str) -> None:
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "--no-verify", "-m", message)


def push(repo: Path, branch: str, remote: str = "origin") -> bool:
    proc = run_git(repo, "push", "--quiet", remote, branch, check=False)
    return proc.returncode == 0


def log_oneline(repo: Path, n: int = 20) -> str:
    return run_git(repo, "log", "--oneline", "--graph", f"-{n}", check=False).stdout
