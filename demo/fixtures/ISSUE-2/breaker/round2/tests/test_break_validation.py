import unittest

from splitsathi.ledger import GroupLedger


class TestInputValidation(unittest.TestCase):
    """Spec guarantee: the ledger rejects nonsense instead of corrupting state."""

    def test_negative_amount_rejected(self):
        ledger = GroupLedger(["Asha", "Vikram"])
        with self.assertRaises(ValueError):
            ledger.add_expense("Asha", -500)

    def test_zero_amount_rejected(self):
        ledger = GroupLedger(["Asha", "Vikram"])
        with self.assertRaises(ValueError):
            ledger.add_expense("Asha", 0)

    def test_unknown_payer_rejected(self):
        ledger = GroupLedger(["Asha", "Vikram"])
        with self.assertRaises(ValueError):
            ledger.add_expense("Mallory", 500)

    def test_unknown_participant_rejected(self):
        ledger = GroupLedger(["Asha", "Vikram"])
        with self.assertRaises(ValueError):
            ledger.add_expense("Asha", 500, ["Asha", "Mallory"])


if __name__ == "__main__":
    unittest.main()
