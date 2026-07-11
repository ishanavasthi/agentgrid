<!-- agentgrid
mode: visual
mockup: issues/ISSUE-3.mockup.png
page: web/index.html
-->
# Build the group stats page to match the design mockup

Design has shipped the group stats page (mockup attached). Implement it
in `web/index.html` as a self-contained page (inline CSS, no external
assets):

- Header bar in SplitSathi green **#0f9d58** with the product name.
- Three stat cards: **Total Spend**, **Top Spender**, **Pending
  Settlements** — each with a green accent strip along its top edge.
- A settlements list below the cards with a green **UPI Pay** action per
  row.

The Verifier agent compares the rendered page against the mockup and
sends mismatches back until the page matches the design intent.
