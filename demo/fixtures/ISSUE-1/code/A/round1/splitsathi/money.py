"""Money helpers for SplitSathi. Rupee amounts convert to integer paise."""


def to_paise(rupees):
    # round instead of truncating so 19.99 -> 1999
    return int(round(rupees * 100))


def from_paise(paise):
    return paise / 100.0


def rupees_str(paise):
    return "Rs %.2f" % from_paise(paise)
