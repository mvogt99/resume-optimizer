

def test_clamp_above_hi():
    from audit_target import clamp
    result = clamp(5.0, 0.0, 3.0)
    assert result == 3.0, f"clamp(5.0, 0.0, 3.0) should be 3.0, got {result}"


def test_clamp_below_lo():
    from audit_target import clamp
    result = clamp(-1.0, 0.0, 3.0)
    assert result == 0.0, f"clamp(-1.0, 0.0, 3.0) should be 0.0, got {result}"
