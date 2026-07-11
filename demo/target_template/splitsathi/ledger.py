"""Group expense ledger for SplitSathi."""


def equal_shares(total_paise, n):
    share = total_paise // n
    return [share] * n


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
