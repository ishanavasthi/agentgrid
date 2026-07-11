# feat(web): group stats page matching the shipped design mockup

## What & Why
Design shipped the group stats mockup; this implements it as a fully
self-contained `web/index.html` — green #0f9d58 header, three stat cards
(Total Spend, Top Spender, Pending Settlements) with accent strips, and a
settlements list with a UPI Pay action per row.

## How it was built
The Coder implemented from the attached mockup; the **Verifier agent**
compared the rendered page against the design and rejected round 1 with
four concrete mismatches (wrong header color, missing third card, missing
accent strips, missing UPI actions). Round 2 addressed all findings and
the Verifier confirmed **match**.

## Test evidence
Unit suite untouched and green; visual verification verdict: match.
