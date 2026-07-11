"""Settlement: turn group balances into a minimal set of transfers."""


def settle(balances):
    """Greedy matcher: largest creditor absorbs largest debtor first.

    Returns a list of (debtor, creditor, amount_paise) transfers.
    Deterministic: ties break on member name.
    """
    creditors = [[m, b] for m, b in sorted(balances.items(),
                                           key=lambda kv: (-kv[1], kv[0])) if b > 0]
    debtors = [[m, -b] for m, b in sorted(balances.items(),
                                          key=lambda kv: (kv[1], kv[0])) if b < 0]
    transfers = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, creditor = debtors[i], creditors[j]
        amount = min(debtor[1], creditor[1])
        transfers.append((debtor[0], creditor[0], amount))
        debtor[1] -= amount
        creditor[1] -= amount
        if debtor[1] == 0:
            i += 1
        if creditor[1] == 0:
            j += 1
    return transfers
