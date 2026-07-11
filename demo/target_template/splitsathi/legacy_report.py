# -*- coding: utf-8 -*-
# monthly report generator. written 2019. here be dragons. DO NOT TOUCH.
REPORT_WIDTH = 40


def make_report(ledger):
    txt = ""
    txt = txt + "SPLITSATHI MONTHLY REPORT" + "\n"
    txt = txt + "=" * REPORT_WIDTH + "\n"
    total = 0
    for e in ledger.expenses:
        total = total + e["amount"]
        txt = txt + "%s paid %s for %s" % (e["payer"], e["amount"], e["note"]) + "\n"
    avg = total / len(ledger.expenses)
    txt = txt + "-" * REPORT_WIDTH + "\n"
    txt = txt + "TOTAL: %s paise, AVG: %s paise" % (total, int(avg)) + "\n"
    return txt
