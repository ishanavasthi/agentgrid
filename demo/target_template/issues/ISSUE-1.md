<!-- agentgrid
mode: standard
-->
# Paisa-level settlement errors + missing UPI settlement summary

Two related problems reported by our pilot groups in Bengaluru:

**1. Money disappears at the paisa level (bug).**
`to_paise(19.99)` returns `1998` — a paisa short. Float truncation is
corrupting conversions. Currency math must be exact: accept int, float
and string amounts (UPI CSV exports arrive as strings), reject sub-paisa
precision like `1.005` with `ValueError`, and add regression tests for
the reported values.

**2. No shareable settlement summary (feature).**
After `settle()`, users want a copy-pasteable summary for their UPI
group chats. Add `format_inr(paise)` rendering Indian digit grouping
(`₹12,34,567.89`) and `settlement_summary(transfers)` producing lines
like `Vikram → Asha: ₹6,17,283.95 (UPI)`, with tests.

Both land in `splitsathi/money.py` — plan accordingly.
