# fix(money): exact paisa conversion + UPI settlement summaries

## What & Why
Pilot groups reported paisa-level corruption (`to_paise(19.99) → 1998`)
and asked for a shareable settlement summary for UPI group chats. This PR
makes currency conversion Decimal-exact (int/float/str inputs, sub-paisa
rejected with `ValueError`) and adds `format_inr` (Indian digit grouping,
`₹12,34,567.89`) plus `settlement_summary` (UPI-ready transfer lines).

## How it was built
Two Coder agents worked the subtasks **in parallel git worktrees**. The
Reviewer rejected the first precision fix (float `round()` is not exact
money math) and the Coder rebuilt it on `Decimal`. Both branches modified
`splitsathi/money.py`; the Integrator agent resolved the resulting merge
conflict, preserving both the exact conversion and the new formatting API.

## Test evidence
Full suite green after integration: baseline tests plus new regression
tests for the 19.99 truncation, string amounts, large values, sub-paisa
rejection, Indian grouping (lakh/crore), and summary output.
