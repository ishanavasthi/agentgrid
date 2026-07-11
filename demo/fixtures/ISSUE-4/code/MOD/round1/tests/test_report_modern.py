import unittest

from splitsathi.ledger import GroupLedger
from splitsathi.legacy_report import make_report


class TestModernReport(unittest.TestCase):
    def test_empty_group_no_longer_crashes(self):
        ledger = GroupLedger(["Asha", "Vikram"])
        report = make_report(ledger)
        self.assertIn("SPLITSATHI MONTHLY REPORT", report)
        self.assertIn("No expenses recorded.", report)

    def test_output_format_preserved(self):
        ledger = GroupLedger(["Asha", "Vikram"])
        ledger.add_expense("Asha", 3000, note="dinner")
        ledger.add_expense("Vikram", 2000, note="cab")
        report = make_report(ledger)
        self.assertIn("Asha paid 3000 for dinner", report)
        self.assertIn("TOTAL: 5000 paise, AVG: 2500 paise", report)


if __name__ == "__main__":
    unittest.main()
