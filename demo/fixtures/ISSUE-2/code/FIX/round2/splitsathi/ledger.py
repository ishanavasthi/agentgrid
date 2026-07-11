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
        if not isinstance(amount_paise, int) or amount_paise <= 0:
            raise ValueError("amount must be a positive integer number of paise, "
                             "got %r" % (amount_paise,))
        if payer not in self.balances:
            raise ValueError("payer %r is not a member of this group" % (payer,))
        participants = list(participants) if participants is not None else list(self.members)
        if not participants:
            raise ValueError("an expense needs at least one participant")
        for member in participants:
            if member not in self.balances:
                raise ValueError("participant %r is not a member of this group"
                                 % (member,))
        shares = equal_shares(amount_paise, len(participants))
        for member, share in zip(participants, shares):
            self.balances[member] -= share
        self.balances[payer] += amount_paise
        self.expenses.append({"payer": payer, "amount": amount_paise,
                              "participants": participants, "note": note})
