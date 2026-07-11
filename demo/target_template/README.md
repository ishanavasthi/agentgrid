# SplitSathi

Group expense splitting for Bharat — split bills, track balances in exact
paise, settle up over UPI.

This is the **target repository** the AgentGrid pipeline operates on. It
ships with a passing test suite and four planted issues under `issues/`:

| issue    | mode        | what's really in there                                   |
|----------|-------------|----------------------------------------------------------|
| ISSUE-1  | standard    | paisa truncation bug + settlement-summary feature (the two subtasks collide in `money.py` → engineered merge conflict) |
| ISSUE-2  | adversarial | `equal_shares` leaks remainder paise; zero input validation |
| ISSUE-3  | visual      | stats page must match `issues/ISSUE-3.mockup.png`         |
| ISSUE-4  | voice       | audio bug report; `legacy_report.py` is 2019-vintage and crashes on empty groups |

Run the suite: `python3 -m unittest discover -s tests -t . -v`
