import unittest

from splitsathi.money import format_inr, settlement_summary


class TestInrFormatting(unittest.TestCase):
    def test_small_amount(self):
        self.assertEqual(format_inr(1050), "₹10.50")

    def test_lakh_grouping(self):
        self.assertEqual(format_inr(123456789), "₹12,34,567.89")

    def test_crore_and_beyond(self):
        self.assertEqual(format_inr(1234567890123), "₹12,34,56,78,901.23")

    def test_negative(self):
        self.assertEqual(format_inr(-2500), "-₹25.00")


class TestSettlementSummary(unittest.TestCase):
    def test_upi_lines(self):
        out = settlement_summary([("Vikram", "Asha", 61728395),
                                  ("Priya", "Asha", 1000)])
        self.assertIn("Vikram → Asha: ₹6,17,283.95 (UPI)", out)
        self.assertIn("Priya → Asha: ₹10.00 (UPI)", out)

    def test_settled_group(self):
        self.assertEqual(settlement_summary([]), "All settled up!")


if __name__ == "__main__":
    unittest.main()
