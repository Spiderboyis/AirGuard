"""The number guard must accept paraphrased tool numbers and reject invented ones."""

from airguard.agent.guard import check

TOOLS = [{"recommended": {"route": "r2 via Ring Road", "leave_at_ist": "09:45", "wait_min": 45,
                          "exposure_index": 120.4, "avg_pm25": 96, "confidence": 0.71},
          "change_vs_fastest_now": {"exposure_pct": -28.3, "arrival_later_min": 49}}]


def test_accepts_grounded_numbers():
    ok, bad = check("Leave at 09:45 via Ring Road: exposure falls 28% (index 120.4), arriving 49 min later. "
                    "Average PM2.5 about 96 µg/m³, confidence 0.71.", TOOLS)
    assert ok, bad


def test_rejects_invented_numbers():
    ok, bad = check("Leave at 10:30 and you cut exposure by 55%.", TOOLS)
    assert not ok
    assert "55" in bad and "10:30" in bad


def test_user_numbers_are_allowed():
    ok, _ = check("You said you can wait 90 minutes; the best option needs 45.", TOOLS, "I can wait 90 minutes")
    assert ok


def test_small_counts_are_safe():
    ok, _ = check("I compared 3 routes for PM2.5.", TOOLS)
    assert ok


def test_fraction_as_percentage():
    ok, bad = check("Confidence is 71%.", TOOLS)
    assert ok, bad
