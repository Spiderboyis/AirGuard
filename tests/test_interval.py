from ml.features import interval


def test_interval_invariant_near_zero():
    for p in (0.0, 0.5, 3.0, 80.0):
        for q10, q90 in ((-20, 10), (-5, -2), (2, 9), (-1, 1)):
            lo, hi = interval(p, q10, q90)
            assert 0 <= lo <= p <= hi
