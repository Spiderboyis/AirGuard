from datetime import date, datetime

from ingestion.fires import sector_table, upwind_count


def test_fire_due_north_counts_as_upwind_the_next_day():
    station = {"id": "s", "lat": 28.6, "lon": 77.2}
    start = date(2026, 10, 1)
    fires = [{"lat": 30.0, "lon": 77.2, "day": start}]
    table = sector_table([station], fires, start, date(2026, 10, 3))
    # The detection is complete on 1 Oct, so it is visible on 2 Oct, not on 1 Oct.
    assert upwind_count(table, "s", start, datetime(2026, 10, 1, 8), 0) == 0
    assert upwind_count(table, "s", start, datetime(2026, 10, 2, 8), 0) == 1
    assert upwind_count(table, "s", start, datetime(2026, 10, 2, 8), 180) == 0


def test_empty_fire_list_is_zero():
    station = {"id": "s", "lat": 28.6, "lon": 77.2}
    table = sector_table([station], [], date(2026, 10, 1), date(2026, 10, 2))
    assert upwind_count(table, "s", date(2026, 10, 1), datetime(2026, 10, 2), 90) == 0
