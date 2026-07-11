"""Group expense ledger for SplitSathi."""


def equal_shares(total_paise, n):
    """Split exactly: remainder paise go to the first members, deterministically."""
    base, remainder = divmod(total_paise, n)
    return [base + 1 if i < remainder else base for i in range(n)]


class GroupLedger:
    def __init__(self, members):
        self.members = list(members)
        self.balances = {m: 0 for m in self.members}
        self.expenses = []

    def add_expense(self, payer, amount_paise, participants=None, note=""):
        participants = participants or self.members
        shares = equal_shares(amount_paise, len(participants))
        for member, share in zip(participants, shares):
            self.balances[member] -= share
        self.balances[payer] += amount_paise
        self.expenses.append({"payer": payer, "amount": amount_paise,
                              "participants": list(participants), "note": note})
