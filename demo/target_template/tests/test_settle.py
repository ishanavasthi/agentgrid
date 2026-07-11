import unittest

from splitsathi.settle import settle


class TestSettle(unittest.TestCase):
    def test_two_debtors_one_creditor(self):
        balances = {"Asha": 2000, "Vikram": -1000, "Priya": -1000}
        self.assertEqual(settle(balances),
                         [("Priya", "Asha", 1000), ("Vikram", "Asha", 1000)])

    def test_settled_group_needs_no_transfers(self):
        self.assertEqual(settle({"Asha": 0, "Vikram": 0}), [])

    def test_single_pair(self):
        self.assertEqual(settle({"Asha": 500, "Vikram": -500}),
                         [("Vikram", "Asha", 500)])


if __name__ == "__main__":
    unittest.main()
