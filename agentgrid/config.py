"""Configuration: paths, .env loading, settings resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = PROJECT_ROOT / "demo"
TEMPLATE_DIR = DEMO_DIR / "target_template"
FIXTURES_DIR = DEMO_DIR / "fixtures"
RUNS_DIR = PROJECT_ROOT / "runs"
ORIGIN_BARE = RUNS_DIR / "demo-origin.git"

_dotenv_loaded = False


def load_dotenv(path: Path | None = None) -> None:
    """Tiny stdlib .env loader; never overrides variables already set."""
    global _dotenv_loaded
    if _dotenv_loaded and path is None:
        return
    _dotenv_loaded = True
    env_path = path or (PROJECT_ROOT / ".env")
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class Settings:
    backend_pref: str = "auto"
    model: str = "gemini-3.5-flash"
    base_agent: str = "antigravity-preview-05-2026"
    api_key: str = ""
    github_repo: str = ""
    mock_delay: float = 0.0
    port: int = 8765
    extra: dict = field(default_factory=dict)

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)


def settings() -> Settings:
    load_dotenv()
    return Settings(
        backend_pref=os.environ.get("AGENTGRID_BACKEND", "auto").strip().lower(),
        model=os.environ.get("AGENTGRID_MODEL", "gemini-3.5-flash").strip(),
        base_agent=os.environ.get(
            "AGENTGRID_BASE_AGENT", "antigravity-preview-05-2026"
        ).strip(),
        api_key=os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GOOGLE_API_KEY", "").strip(),
        github_repo=os.environ.get("GITHUB_REPO", "").strip(),
        mock_delay=float(os.environ.get("AGENTGRID_MOCK_DELAY", "0") or 0),
        port=int(os.environ.get("AGENTGRID_PORT", "8765") or 8765),
    )
