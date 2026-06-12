import datetime

from sport_slot.services.availability import compute_slots

FACILITY = {"slot_duration_minutes": 60, "open_time": "06:00",
            "close_time": "22:00"}


def _now(day, hh, mm=0):
    return datetime.datetime(2026, 6, day, hh, mm)


def test_sixteen_slots_generated():
    slots = compute_slots(FACILITY, datetime.date(2026, 6, 12), set(),
                          _now(12, 5), 1, "20:00")
    assert len(slots) == 16
    assert slots[0]["start"] == "06:00" and slots[-1]["end"] == "22:00"


def test_today_past_and_available_split():
    slots = compute_slots(FACILITY, datetime.date(2026, 6, 12), set(),
                          _now(12, 14, 0), 1, "20:00")
    by = {s["start"]: s for s in slots}
    assert by["09:00"]["status"] == "past" and not by["09:00"]["bookable"]
    assert by["15:00"]["bookable"] is True
    # 13:00-14:00 ended exactly now → past
    assert by["13:00"]["status"] == "past"


def test_booked_slot_marked():
    slots = compute_slots(FACILITY, datetime.date(2026, 6, 12),
                          {"18:00"}, _now(12, 5), 1, "20:00")
    by = {s["start"]: s for s in slots}
    assert by["18:00"]["status"] == "booked"
    assert by["18:00"]["reason"] == "BOOKED"
    assert by["17:00"]["bookable"] is True


def test_tomorrow_before_window_not_bookable():
    slots = compute_slots(FACILITY, datetime.date(2026, 6, 13), set(),
                          _now(12, 19, 59), 1, "20:00")
    assert all(not s["bookable"] for s in slots)
    assert slots[0]["reason"] == "WINDOW_NOT_OPEN"
    assert slots[0]["status"] == "available"


def test_tomorrow_after_window_bookable():
    slots = compute_slots(FACILITY, datetime.date(2026, 6, 13), set(),
                          _now(12, 20, 0), 1, "20:00")
    assert all(s["bookable"] for s in slots)


def test_beyond_horizon():
    slots = compute_slots(FACILITY, datetime.date(2026, 6, 20), set(),
                          _now(12, 21), 1, "20:00")
    assert all(s["reason"] == "BEYOND_HORIZON" for s in slots)


def test_past_date_all_past():
    slots = compute_slots(FACILITY, datetime.date(2026, 6, 10), set(),
                          _now(12, 9), 1, "20:00")
    assert all(s["status"] == "past" for s in slots)


def test_wider_horizon_midrange_open():
    slots = compute_slots(FACILITY, datetime.date(2026, 6, 15), set(),
                          _now(12, 6), 7, "20:00")
    assert all(s["bookable"] for s in slots)


def test_in_progress_slot_bookable_and_marked():
    slots = compute_slots(FACILITY, datetime.date(2026, 6, 12), set(),
                          _now(12, 14, 30), 1, "20:00")
    by = {s["start"]: s for s in slots}
    assert by["14:00"]["bookable"] is True
    assert by["14:00"]["reason"] == "IN_PROGRESS"
    assert by["13:00"]["status"] == "past"
