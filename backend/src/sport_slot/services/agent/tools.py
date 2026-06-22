"""Agent tool schemas — plain dicts only, zero google imports.

Registered tools: check_availability, list_my_bookings, book.
cancel is NOT registered (capability not yet implemented).
"""

from __future__ import annotations

CHECK_AVAILABILITY: dict = {
    "name": "check_availability",
    "description": (
        "Check available booking slots for a specific facility on a given date. "
        "Use this when the user asks about free times or availability."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "facility_id": {
                "type": "string",
                "description": "The unique ID of the facility to check.",
            },
            "date": {
                "type": "string",
                "description": "The date to check in YYYY-MM-DD format.",
            },
        },
        "required": ["facility_id", "date"],
    },
}

LIST_MY_BOOKINGS: dict = {
    "name": "list_my_bookings",
    "description": (
        "List the current user's upcoming and recent bookings. "
        "Use this when the user asks about their reservations."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of bookings to return (default 10).",
            },
        },
        "required": [],
    },
}

BOOK: dict = {
    "name": "book",
    "description": (
        "Book a specific facility, date, and time slot after the user has chosen. "
        "The system will ask the user to confirm before the booking is created."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "facility_id": {
                "type": "string",
                "description": "The unique ID of the facility to book.",
            },
            "date": {
                "type": "string",
                "description": "The date to book in YYYY-MM-DD format.",
            },
            "start": {
                "type": "string",
                "description": "The start time to book in HH:MM format.",
            },
        },
        "required": ["facility_id", "date", "start"],
    },
}

REGISTERED_TOOLS: list[dict] = [CHECK_AVAILABILITY, LIST_MY_BOOKINGS, BOOK]
