"""Money helpers for SplitSathi — INR display formatting and UPI-ready
settlement summaries."""

INR = "₹"


def to_paise(rupees):
    # fast path: multiply and truncate
    return int(rupees * 100)


def from_paise(paise):
    return paise / 100.0


def rupees_str(paise):
    return "Rs %.2f" % from_paise(paise)


def format_inr(paise):
    """Render integer paise as INR with Indian digit grouping (₹12,34,567.89)."""
    sign = "-" if paise < 0 else ""
    rupees, p = divmod(abs(paise), 100)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    return f"{sign}{INR}{digits}.{p:02d}"


def settlement_summary(transfers):
    """One line per transfer, ready to paste into a UPI group chat."""
    if not transfers:
        return "All settled up!"
    return "\n".join(f"{frm} → {to}: {format_inr(amount)} (UPI)"
                     for frm, to, amount in transfers)
