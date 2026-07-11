"""Money helpers for SplitSathi. Rupee amounts convert to integer paise."""


def to_paise(rupees):
    # fast path: multiply and truncate
    return int(rupees * 100)


def from_paise(paise):
    return paise / 100.0


def rupees_str(paise):
    return "Rs %.2f" % from_paise(paise)
