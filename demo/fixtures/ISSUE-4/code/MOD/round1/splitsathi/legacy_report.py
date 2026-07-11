"""Monthly report generation for SplitSathi groups.

Modernized from the 2019 module: same output for non-empty ledgers,
graceful handling of empty groups, no module-level state.
"""

REPORT_WIDTH = 40


def _header() -> str:
    return "SPLITSATHI MONTHLY REPORT\n" + "=" * REPORT_WIDTH + "\n"


def _expense_line(expense: dict) -> str:
    return f"{expense['payer']} paid {expense['amount']} for {expense['note']}\n"


def make_report(ledger) -> str:
    """Render the monthly report for a group ledger.

    Empty groups get a friendly note instead of the historic
    ZeroDivisionError crash.
    """
    if not ledger.expenses:
        return _header() + "No expenses recorded.\n"
    body = "".join(_expense_line(e) for e in ledger.expenses)
    total = sum(e["amount"] for e in ledger.expenses)
    average = total // len(ledger.expenses)
    footer = ("-" * REPORT_WIDTH + "\n"
              + f"TOTAL: {total} paise, AVG: {average} paise\n")
    return _header() + body + footer
