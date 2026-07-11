import unittest

from splitsathi.ledger import GroupLedger, equal_shares


class TestMoneyConservation(unittest.TestCase):
    """Spec guarantee: paise never appear or vanish during a split."""

    def test_shares_sum_to_total(self):
        self.assertEqual(sum(equal_shares(10000, 3)), 10000)

    def test_balances_net_zero_for_uneven_split(self):
        ledger = GroupLedger(["Asha", "Vikram", "Priya"])
        ledger.add_expense("Asha", 10000, note="auto, 100 rupees, 3 ways")
        self.assertEqual(sum(ledger.balances.values()), 0)


if __name__ == "__main__":
    unittest.main()
