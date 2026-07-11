# refactor(report): modernize legacy monthly report, fix empty-group crash

## What & Why
Filed by **voice note in Hinglish** — the Intake agent transcribed,
translated and structured it into this issue. `legacy_report.py`
(2019-vintage) crashed with `ZeroDivisionError` on groups with no
expenses. Modernized to clean f-string helpers; empty groups now get a
friendly "No expenses recorded." report; output for non-empty ledgers is
preserved exactly.

## How it was built
Intake (audio → structured issue) → Planner → Coder (worktree branch) →
Reviewer (approved: output-compat verified against the pre-existing
report test) → Tester → this PR. Legacy-modernization is the exact flow
Indian IT services run at scale — this pipeline automates it end to end.

## Test evidence
Full suite green: historic `test_report` output check plus new
regression tests for the empty-group path and format preservation.
