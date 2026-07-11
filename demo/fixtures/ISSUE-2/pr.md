# fix(ledger): conserve every paisa and reject invalid expenses

## What & Why
Splitting ₹100 three ways leaked a paisa (`equal_shares` dropped the
division remainder), and `GroupLedger` accepted negative amounts and
strangers, silently corrupting balances. Both are now impossible.

## How it was built
Adversarial TDD between two agents. Round 1: the **Breaker** planted
conservation tests (shares must sum to the total; balances must net to
zero) — red; the **Coder** fixed remainder distribution — green. Round 2:
the Breaker attacked the trust boundary (negative/zero amounts, unknown
payer/participants) — red; the Coder added strict validation — green.
Round 3: the Breaker found no further legitimate attack and **conceded**.

## Test evidence
Final suite green including every Breaker test; no test was weakened or
removed.
