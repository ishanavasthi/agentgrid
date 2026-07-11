"""Filesystem tools, hard-confined to a repo root (no path escapes)."""

from __future__ import annotations

from pathlib import Path

from ..errors import ToolError
from .base import ToolSpec

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}


def safe_path(root: Path, rel: str) -> Path:
    root = Path(root).resolve()
    p = (root / rel).resolve()
    if p != root and root not in p.parents:
        raise ToolError(f"path escapes the workspace: {rel!r}")
    return p


def make_fs_tools(root: Path) -> list[ToolSpec]:
    root = Path(root).resolve()

    def read_file(path: str) -> str:
        p = safe_path(root, path)
        if not p.exists():
            raise ToolError(f"no such file: {path}")
        return p.read_text(encoding="utf-8")

    def write_file(path: str, content: str) -> str:
        p = safe_path(root, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"wrote {len(content)} chars to {path}"

    def list_files(subdir: str = "") -> str:
        base = safe_path(root, subdir or ".")
        if not base.exists():
            raise ToolError(f"no such directory: {subdir}")
        out = []
        for p in sorted(base.rglob("*")):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if p.is_file():
                out.append(str(p.relative_to(root)))
            if len(out) >= 300:
                out.append("...[listing capped at 300]")
                break
        return "\n".join(out) or "(empty)"

    return [
        ToolSpec(
            name="read_file",
            description="Read a UTF-8 text file from the repository. Path is relative to repo root.",
            parameters={"type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]},
            fn=read_file),
        ToolSpec(
            name="write_file",
            description=("Create or fully overwrite a UTF-8 text file in the repository. "
                         "Always write the COMPLETE file content. Path is relative to repo root."),
            parameters={"type": "object",
                        "properties": {"path": {"type": "string"},
                                       "content": {"type": "string"}},
                        "required": ["path", "content"]},
            fn=write_file),
        ToolSpec(
            name="list_files",
            description="Recursively list files in the repository (or a subdirectory).",
            parameters={"type": "object",
                        "properties": {"subdir": {"type": "string"}},
                        "required": []},
            fn=list_files),
    ]
