"""Money helpers for SplitSathi — exact Decimal-based paise conversion."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def to_paise(rupees):
    """Convert a rupee amount (int, float or str) to integer paise, exactly."""
    try:
        amount = Decimal(str(rupees))
    except InvalidOperation:
        raise ValueError("not a money amount: %r" % (rupees,)) from None
    paise = amount * 100
    quantized = paise.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if quantized != paise:
        raise ValueError("sub-paisa precision not allowed: %r" % (rupees,))
    return int(quantized)


def from_paise(paise):
    return paise / 100.0


def rupees_str(paise):
    return f"Rs {from_paise(paise):.2f}"
