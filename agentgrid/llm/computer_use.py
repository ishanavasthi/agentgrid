"""Interactive Computer Use verification loop (Functionality #8 upgrade).

Drives Gemini 3.5 Flash's `computer_use` browser-environment tool (see
COMPUTER_USE.md) against a real, sandboxed local page: the model decides
each action from a screenshot, Playwright (`agentgrid/tools/computer_use.
BrowserSession`) executes it, a fresh screenshot goes back, repeat until
the model stops calling tools and returns a plain-text verdict.

Deliberately self-contained and NOT routed through the shared
`LLMBackend`/`Agent.run()` tool loop used by every other role — Computer
Use needs a screenshot bundled into every function response, which that
generic interface doesn't carry, and this keeps the change surface small
next to an already-validated core. Any failure here (missing SDK,
missing Playwright, model/API error, safety block, sandbox violation) is
meant to be caught by the caller and treated as "fall back to the
static-screenshot Verifier" — this must never be the only way visual
mode can pass.
"""

from __future__ import annotations

from pathlib import Path

from ..tools.computer_use import BrowserSession, ComputerUseError
from .base import call_with_retry
from .gemini import _load_sdk

MAX_TURNS = 10
COMPUTER_USE_MODEL = "gemini-3.5-flash"

# Scoped to this narrow use case (observe + click a local static demo
# page) rather than Google's full example — there is no real payment,
# comms, or account-creation surface here, but the same "stop and report
# instead of proceeding" posture applies to anything unexpected.
SYSTEM_INSTRUCTION = """You are a QA agent verifying a small local demo
web page against a task description, using the computer_use browser
tool. You may only observe and interact with the page already open
(clicking, scrolling, reading rendered text) to check whether it matches
the given specification — you are not automating a real task.

RULES (non-negotiable):
- Never navigate to any URL outside the page you were given.
- Never submit forms, send data, or agree to anything — this is a
  read-only visual/behavioral check.
- If any action would require confirmation or seems consequential, stop
  and report what you found instead of proceeding.
- When you are done observing (usually within a few actions), STOP
  calling tools and reply with plain text only, in exactly this format:
  VERDICT: match
  ISSUES: none
  or
  VERDICT: mismatch
  ISSUES:
  - <concrete mismatch 1>
  - <concrete mismatch 2>
"""


def run_interactive_verify(settings, page_path: Path, task_prompt: str,
                            max_turns: int = MAX_TURNS,
                            reference_image: Path | None = None) -> dict:
    """Returns {"verdict", "issues", "steps", "transcript"}.

    Raises ComputerUseError / any SDK exception on failure — callers
    must catch and fall back, never let this be the sole verify path.
    `reference_image`, if given (e.g. a design mockup), is attached
    alongside the initial live screenshot so the model can compare them
    while it interacts with the live page.
    """
    genai, types = _load_sdk()
    client = genai.Client(api_key=settings.api_key)

    resolved = Path(page_path).resolve()
    target_url = f"file://{resolved}"
    allowed_prefix = f"file://{resolved.parent}"

    session = BrowserSession(allowed_prefix=allowed_prefix)
    try:
        session.goto(target_url)
        shot = session.screenshot()

        tool = types.Tool(computer_use=types.ComputerUse(
            environment=types.Environment.ENVIRONMENT_BROWSER,
            enable_prompt_injection_detection=True))
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION, tools=[tool])

        first_parts = [
            types.Part(text=task_prompt),
            types.Part(text="Live page (browser you are controlling):"),
            types.Part(inline_data=types.Blob(mime_type="image/png", data=shot)),
        ]
        if reference_image is not None and Path(reference_image).exists():
            first_parts.insert(1, types.Part(text="Target design mockup for comparison:"))
            first_parts.insert(2, types.Part(inline_data=types.Blob(
                mime_type="image/png", data=Path(reference_image).read_bytes())))
        contents = [types.Content(role="user", parts=first_parts)]

        transcript = []
        for turn in range(max_turns):
            response = call_with_retry(
                lambda: client.models.generate_content(
                    model=COMPUTER_USE_MODEL, contents=contents, config=config),
                what="computer-use")
            candidate = response.candidates[0]
            parts = candidate.content.parts or []
            fn_parts = [p for p in parts if getattr(p, "function_call", None)]

            if not fn_parts:
                final_text = "\n".join(p.text for p in parts if getattr(p, "text", None))
                verdict, issues = _parse_verdict(final_text)
                return {"verdict": verdict, "issues": issues,
                        "steps": turn, "transcript": transcript}

            contents.append(candidate.content)  # preserves thought_signature verbatim

            response_parts = []
            for part in fn_parts:
                fc = part.function_call
                args = dict(fc.args or {})
                safety = args.pop("safety_decision", None)
                transcript.append({"action": fc.name, "args": args,
                                   "intent": args.get("intent", "")})
                if safety and str(safety.get("decision", "")).lower() not in (
                        "regular", "allowed", ""):
                    return {"verdict": "mismatch", "steps": turn,
                            "transcript": transcript,
                            "issues": [f"stopped: action {fc.name!r} needed "
                                       f"confirmation ({safety.get('explanation', '')})"]}
                result = session.execute(fc.name, args)
                response_parts.append(types.Part(function_response=types.FunctionResponse(
                    id=getattr(fc, "id", None), name=fc.name, response={"result": result})))

            new_shot = session.screenshot()
            response_parts.append(types.Part(
                inline_data=types.Blob(mime_type="image/png", data=new_shot)))
            contents.append(types.Content(role="user", parts=response_parts))

        return {"verdict": "mismatch", "steps": max_turns, "transcript": transcript,
                "issues": ["stopped: exceeded max turns without a verdict"]}
    finally:
        session.close()


def _parse_verdict(text: str) -> tuple[str, list[str]]:
    lowered = text.lower()
    verdict = "match" if "verdict: match" in lowered else "mismatch"
    issues: list[str] = []
    if "ISSUES:" in text:
        tail = text.split("ISSUES:", 1)[1]
        for line in tail.splitlines():
            item = line.strip().lstrip("-").strip()
            if item and item.lower() != "none":
                issues.append(item)
    return verdict, issues
