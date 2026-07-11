"""AgentGrid CLI: setup-demo | run | serve | smoke | doctor | issues."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
from pathlib import Path

from . import __version__
from .bus import BUS
from .errors import AgentGridError
from .config import ORIGIN_BARE, TEMPLATE_DIR, settings as load_settings
from .util import color


# ---------------------------------------------------------- live printer

_AGENT_COLORS = {"Planner": "cyan", "Coder": "blue", "Reviewer": "yellow",
                 "Integrator": "magenta", "Breaker": "red", "Verifier": "cyan",
                 "Intake": "green", "Publisher": "green"}


def _print_event(e: dict) -> None:
    t = e["type"]
    if t == "run_started":
        print(color(f"\n▶ run {e['run_id']}  issue={e['issue']} mode={e['mode']} "
                    f"backend={e['backend']}", "bold"))
        print(color(f"  {e.get('backend_note', '')}", "dim"))
    elif t == "phase":
        print(color(f"\n── {e['name']} " + "─" * max(4, 46 - len(e['name'])), "bold"))
    elif t == "handoff":
        print(color(f"  ⇄ {e['frm']} → {e['to']}: {e.get('task_title', '')}", "magenta"))
    elif t == "agent_message":
        first = (e.get("content") or "").strip().splitlines()
        preview = first[0][:110] if first else ""
        print(f"  {color(e['agent'] + ':', _AGENT_COLORS.get(e['agent'], 'cyan'))} {preview}")
    elif t == "tool_call":
        args = e.get("args", {})
        arg_preview = args.get("path", "") or ""
        print(color(f"    ⚙ {e['agent']} → {e['tool']}({arg_preview})", "dim"))
    elif t == "review_verdict":
        good = e["verdict"] == "approve"
        mark = color("✔ approved", "green") if good else color("✘ changes requested", "red")
        print(f"  🔍 review [{e['sub']}] round {e['round']}: {mark}")
    elif t == "merge_conflict":
        print(color(f"  💥 MERGE CONFLICT on {e['branch']}: {', '.join(e['files'])}", "red"))
    elif t == "test_result":
        c = "green" if e["passed"] else "red"
        print(color(f"  🧪 {e['summary']}  [{e.get('context', '')}]", c))
    elif t == "breaker_result":
        print(color(f"  💣 breaker round {e['round']}: {e['action']} — "
                    f"{e.get('rationale', '')[:90]}", "yellow"))
    elif t == "verify_verdict":
        c = "green" if e["verdict"] == "match" else "yellow"
        print(color(f"  👁 visual round {e['round']}: {e['verdict']} "
                    f"{('— ' + '; '.join(e.get('issues', []))[:120]) if e.get('issues') else ''}", c))
    elif t == "intake_result":
        print(color(f"  🎙 intake: “{e['title']}” "
                    f"[{e.get('detected_language', '')}]", "green"))
    elif t == "pr_created":
        where = e.get("url") or e.get("preview_path", "")
        print(color(f"  📮 PR ({e.get('mode')}): {e.get('title', '')} → {where}", "green"))
    elif t == "error":
        print(color(f"  ✖ {e['message']}", "red"))
    elif t == "run_finished":
        ok = e.get("ok")
        print(color(f"\n■ run finished: {'SUCCESS' if ok else 'FAILED'}",
                    "green" if ok else "red"))


def _with_live_printer(fn):
    q = BUS.subscribe(replay=False)
    stop = threading.Event()

    def pump():
        while not stop.is_set():
            try:
                _print_event(q.get(timeout=0.25))
            except Exception:
                continue

    thread = threading.Thread(target=pump, daemon=True)
    thread.start()
    try:
        return fn()
    finally:
        stop.set()
        thread.join(timeout=1)
        BUS.unsubscribe(q)


# -------------------------------------------------------------- commands

def cmd_setup_demo(args) -> int:
    from .pipeline import Orchestrator
    info = Orchestrator().setup_demo(force=args.force)
    verb = "created" if info.get("created") else "already present (use --force to rebuild)"
    print(f"demo origin {verb}: {info['origin']}")
    if info.get("baseline"):
        print(f"baseline: {info['baseline']}")
    return 0


def cmd_run(args) -> int:
    from .pipeline import Orchestrator
    orch = Orchestrator(backend_name=args.backend)
    summary = _with_live_printer(lambda: orch.run_issue(args.issue, args.mode))
    print("\nsummary:")
    print(json.dumps({k: v for k, v in summary.items() if k != "pr"}, indent=2))
    pr = summary.get("pr", {})
    if pr:
        print(f"PR ({pr.get('mode')}): {pr.get('url') or pr.get('preview_path')}")
    return 0 if summary.get("tests_passed") else 1


def cmd_serve(args) -> int:
    from .server.app import serve
    serve(port=args.port, backend=args.backend)
    return 0


def cmd_smoke(args) -> int:
    from .smoke import run_smoke
    return 0 if run_smoke(verbose=True) else 1


def cmd_issues(args) -> int:
    from .pipeline.orchestrator import parse_frontmatter
    for path in sorted((TEMPLATE_DIR / "issues").glob("*.md")):
        front = parse_frontmatter(path.read_text(encoding="utf-8"))
        print(f"{path.stem:10s} mode={front.get('mode', 'standard')}")
    return 0


def cmd_doctor(args) -> int:
    s = load_settings()
    rows: list[tuple[str, bool, str]] = []

    py_ok = sys.version_info >= (3, 9)
    rows.append((f"python {sys.version.split()[0]}", py_ok,
                 "need >= 3.9 (3.10+ recommended)"))
    rows.append(("git", shutil.which("git") is not None, "brew install git"))
    rows.append(("demo template", TEMPLATE_DIR.exists(), "repo incomplete?"))
    rows.append(("demo origin seeded", ORIGIN_BARE.exists(),
                 "python3 -m agentgrid setup-demo"))
    rows.append(("GEMINI_API_KEY", s.has_key,
                 "put it in .env — mock backend until then"))

    try:
        import google.genai as genai  # type: ignore
        ver = getattr(genai, "__version__", "?")
        sdk_ok = True
        note = f"v{ver} (Managed Agents needs client.agents/interactions — see doctor row below)"
    except ImportError:
        sdk_ok, note = False, "pip install google-genai"
    rows.append(("google-genai SDK", sdk_ok, note))

    if s.has_key and sdk_ok:
        try:
            from google import genai as g2  # type: ignore
            client = g2.Client(api_key=s.api_key)
            ids = []
            for m in client.models.list():
                name = getattr(m, "name", "").split("/")[-1]
                if name.startswith("gemini") and "embedding" not in name:
                    ids.append(name)
                if len(ids) >= 12:
                    break
            rows.append(("API reachable — models: "
                         + (", ".join(ids) or "none listed"),
                         True, f"configured model: {s.model} "
                               "(override per-run: AGENTGRID_MODEL=...)"))
            rows.append(("managed agents surface (client.agents)",
                         hasattr(client, "agents") and hasattr(client, "interactions"),
                         "hybrid falls back to pure function-calling if absent"))
        except Exception as exc:
            rows.append(("API reachability", False, f"{type(exc).__name__}: {exc}"))

    try:
        import playwright  # type: ignore # noqa: F401
        rows.append(("playwright (visual mode screenshots)", True,
                     "run: playwright install chromium (once)"))
    except ImportError:
        rows.append(("playwright (optional)", False,
                     "visual mode falls back to HTML inspection"))
    rows.append(("gh CLI (optional, real PRs)", shutil.which("gh") is not None,
                 "PRs are previewed locally without it"))

    print(color(f"AgentGrid {__version__} doctor", "bold"))
    for label, ok, note in rows:
        mark = color("✓", "green") if ok else color("✗", "yellow")
        suffix = f"  {color('— ' + note, 'dim')}" if (note and not ok) else ""
        print(f" {mark} {label}{suffix}")
    backend_name = s.backend_pref
    print(f"\nbackend preference: {backend_name} "
          f"(resolves to {'live Gemini' if s.has_key else 'mock'} today)")

    if getattr(args, "probe", False):
        if not (s.has_key and sdk_ok):
            print(color("\n--probe needs GEMINI_API_KEY + google-genai installed", "red"))
            return 1
        print(color("\nlive probe (~200 tokens, retries on rate limits)…", "bold"))
        from .llm.gemini import probe_live
        probe_ok = True
        for label, ok, note in probe_live(s):
            mark = color("✓", "green") if ok else color("✗", "red")
            probe_ok &= ok
            print(f" {mark} {label}  {color('— ' + note, 'dim')}")
        print(color("probe PASSED — the live pipeline path works",
                    "green") if probe_ok
              else color("probe FAILED — fix before relying on live runs", "red"))
        return 0 if probe_ok else 1

    print("smoke anytime: python3 -m agentgrid smoke")
    return 0


# ----------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentgrid",
        description="AgentGrid — autonomous multi-agent coding pipeline on Gemini")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("setup-demo", help="seed the SplitSathi demo repo + bare origin")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_setup_demo)

    p = sub.add_parser("run", help="run one issue through the pipeline")
    p.add_argument("--issue", required=True, help="e.g. ISSUE-1")
    p.add_argument("--mode", default="auto",
                   choices=["auto", "standard", "adversarial", "visual", "voice"])
    p.add_argument("--backend", default=None,
                   help="mock | gemini | managed | auto (default: env/auto)")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("serve", help="start the live dashboard")
    p.add_argument("--port", type=int, default=load_settings().port)
    p.add_argument("--backend", default=None)
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("smoke", help="offline end-to-end smoke of all 4 pipelines")
    p.set_defaults(fn=cmd_smoke)

    p = sub.add_parser("doctor", help="environment/dependency checkup")
    p.add_argument("--probe", action="store_true",
                   help="also make 2 tiny live API calls to validate the "
                        "real Gemini path (needs key + SDK; ~200 tokens)")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("issues", help="list demo issues")
    p.set_defaults(fn=cmd_issues)

    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 0
    try:
        return args.fn(args)
    except AgentGridError as exc:
        print(color(f"error: {exc}", "red"))
        return 2
    except KeyboardInterrupt:
        return 130
