"""PR publishing — Functionality #6.

Always writes runs/<id>/pr_preview.md and pushes the branch to the local
bare origin. If GITHUB_REPO is set and the `gh` CLI is authenticated, it
opens a real PR too. Demo never depends on the network.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import gitops


def has_gh() -> bool:
    return shutil.which("gh") is not None


def publish_pr(repo_dir: Path, branch: str, title: str, body: str,
               run_dir: Path, github_repo: str = "") -> dict:
    result = {"mode": "preview", "pushed": False, "url": "", "preview_path": ""}

    preview = run_dir / "pr_preview.md"
    preview.write_text(
        f"# {title}\n\n*branch:* `{branch}`\n\n{body}\n\n---\n"
        f"To open this PR for real:\n"
        f"```bash\ngh pr create --head {branch} --title {title!r} --body-file {preview.name}\n```\n",
        encoding="utf-8")
    result["preview_path"] = str(preview)

    result["pushed"] = gitops.push(repo_dir, branch)

    target = github_repo or os.environ.get("GITHUB_REPO", "")
    if target and has_gh():
        proc = subprocess.run(
            ["gh", "pr", "create", "--repo", target, "--head", branch,
             "--title", title, "--body", body],
            cwd=str(repo_dir), capture_output=True, text=True)
        if proc.returncode == 0:
            result["mode"] = "real"
            result["url"] = proc.stdout.strip().splitlines()[-1] if proc.stdout else ""
        else:
            result["note"] = f"gh pr create failed, kept preview: {proc.stderr.strip()[:300]}"
    return result
