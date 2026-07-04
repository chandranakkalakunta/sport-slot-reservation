import datetime

from sport_slot.services.availability import compute_slots

_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

FACILITY = {
    "slot_duration_minutes": 60,
    "weekly_schedule": {day: [{"start": "06:00", "end": "22:00"}] for day in _DAYS},
}


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


# ── weekly_schedule-specific tests ───────────────────────────────────────────

def test_two_ranges_produce_slots_with_gap():
    # 2026-06-12 = Friday; two ranges 06:00-09:00 and 16:00-21:00.
    # Expects 3 + 5 = 8 slots with no slot in the 09:00-16:00 gap.
    fac = {
        "slot_duration_minutes": 60,
        "weekly_schedule": {day: [{"start": "06:00", "end": "22:00"}] for day in _DAYS},
    }
    fac["weekly_schedule"]["friday"] = [
        {"start": "06:00", "end": "09:00"},
        {"start": "16:00", "end": "21:00"},
    ]
    slots = compute_slots(fac, datetime.date(2026, 6, 12), set(), _now(12, 5), 1, "20:00")
    starts = [s["start"] for s in slots]
    assert len(slots) == 8
    assert starts[:3] == ["06:00", "07:00", "08:00"]
    assert starts[3:] == ["16:00", "17:00", "18:00", "19:00", "20:00"]
    assert "09:00" not in starts and "15:00" not in starts


def test_closed_day_returns_no_slots():
    # 2026-06-10 = Wednesday; Wednesday has an empty range list → closed.
    fac = {
        "slot_duration_minutes": 60,
        "weekly_schedule": {day: [{"start": "06:00", "end": "22:00"}] for day in _DAYS},
    }
    fac["weekly_schedule"]["wednesday"] = []
    slots = compute_slots(fac, datetime.date(2026, 6, 10), set(), _now(10, 5), 7, "00:00")
    assert slots == []


def test_different_days_use_correct_ranges():
    # Monday 2026-06-15: 08:00-12:00 (4 slots).
    # Friday 2026-06-12: 06:00-10:00 (4 slots).
    # Verify each date picks the right day's ranges.
    fac = {
        "slot_duration_minutes": 60,
        "weekly_schedule": {day: [{"start": "00:00", "end": "01:00"}] for day in _DAYS},
    }
    fac["weekly_schedule"]["monday"] = [{"start": "08:00", "end": "12:00"}]
    fac["weekly_schedule"]["friday"] = [{"start": "06:00", "end": "10:00"}]

    monday_slots = compute_slots(fac, datetime.date(2026, 6, 15), set(), _now(15, 5), 7, "00:00")
    friday_slots = compute_slots(fac, datetime.date(2026, 6, 12), set(), _now(12, 5), 7, "00:00")

    assert len(monday_slots) == 4
    assert monday_slots[0]["start"] == "08:00" and monday_slots[-1]["end"] == "12:00"
    assert len(friday_slots) == 4
    assert friday_slots[0]["start"] == "06:00" and friday_slots[-1]["end"] == "10:00"
