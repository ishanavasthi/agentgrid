<!-- agentgrid
mode: adversarial
files: splitsathi/ledger.py
-->
# Group totals don't add up (paise leak) — harden GroupLedger

Community reports: split a ₹100.00 auto ride three ways and the group's
net balance no longer sums to zero — a paisa simply vanishes. Beyond the
arithmetic, `GroupLedger` accepts anything: negative amounts, zero
amounts, payers who aren't in the group.

Money conservation is the core invariant of this product. This issue
runs in **adversarial mode**: the Breaker agent plants legitimate failing
spec tests, the Coder must make them pass without weakening any test,
until the Breaker concedes it can no longer break the ledger.
