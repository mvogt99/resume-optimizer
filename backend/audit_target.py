"""P4B Tier-1 audit target — resume-optimizer side. Will be auto-fixed by support-bot."""


def quadruple_value(x: int) -> int:
    return x * 4


def clamp(value: float, lo: float, hi: float) -> float:
    """Return value clamped to [lo, hi].

    Bug: returns lo when value > hi and hi when value < lo (bounds swapped).
    Expected: clamp(5.0, 0.0, 3.0) == 3.0
    Actual:   clamp(5.0, 0.0, 3.0) == 0.0
    """
    if value < lo:
        return hi  # BUG: should return lo
    if value > hi:
        return hi
    return value
