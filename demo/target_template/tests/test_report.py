import unittest

from splitsathi.ledger import GroupLedger
from splitsathi.legacy_report import make_report


class TestMonthlyReport(unittest.TestCase):
    def test_report_totals(self):
        ledger = GroupLedger(["Asha", "Vikram"])
        ledger.add_expense("Asha", 3000, note="dinner")
        ledger.add_expense("Vikram", 2000, note="cab")
        report = make_report(ledger)
        self.assertIn("SPLITSATHI MONTHLY REPORT", report)
        self.assertIn("Asha paid 3000 for dinner", report)
        self.assertIn("Vikram paid 2000 for cab", report)
        self.assertIn("TOTAL: 5000 paise, AVG: 2500 paise", report)


if __name__ == "__main__":
    unittest.main()
