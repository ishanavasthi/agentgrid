import unittest

from splitsathi.ledger import GroupLedger, equal_shares


class TestEqualShares(unittest.TestCase):
    def test_divisible_split(self):
        self.assertEqual(equal_shares(3000, 3), [1000, 1000, 1000])


class TestGroupLedger(unittest.TestCase):
    def test_balances_after_group_expense(self):
        ledger = GroupLedger(["Asha", "Vikram", "Priya"])
        ledger.add_expense("Asha", 3000, note="chai")
        self.assertEqual(ledger.balances["Asha"], 2000)
        self.assertEqual(ledger.balances["Vikram"], -1000)
        self.assertEqual(ledger.balances["Priya"], -1000)
        self.assertEqual(sum(ledger.balances.values()), 0)

    def test_partial_participants(self):
        ledger = GroupLedger(["Asha", "Vikram", "Priya"])
        ledger.add_expense("Asha", 3000, note="chai")
        ledger.add_expense("Vikram", 1200, ["Asha", "Vikram"], note="auto")
        self.assertEqual(ledger.balances["Asha"], 1400)
        self.assertEqual(ledger.balances["Vikram"], -400)
        self.assertEqual(ledger.balances["Priya"], -1000)
        self.assertEqual(len(ledger.expenses), 2)


if __name__ == "__main__":
    unittest.main()
