"""Agent orchestrator — propose (read + book/cancel intent) and execute (confirm) paths.

ADR-0021 §2/§3/§4, ADR-0022 §5/§8.

Propose flow (run_agent):
1. Build system prompt with tenant facilities + today's date.
2. Call Vertex (generate) — may return a function_call or text.
3. If function_call:
   - read-only (check_availability, list_my_bookings, get_my_preferences,
     get_my_invoices, get_my_current_month_charges): dispatch service,
     Turn 2 for NL reply, output guard.
   - book: hallucination-guard facility_id, read-validate slot is bookable,
     propose-time quota check, write pending action, return deterministic
     confirm prompt + pending_action_id. (NO Vertex Turn 2, NO mutation on propose.)
   - cancel: deterministic Python filter (sport + date_hint), 0/1/many branching.
     0 cancellable + 0 too_late → not-found reply.
     0 cancellable + ≥1 too_late → past-cutoff reply.
     1 cancellable → propose pending action.
     ≥2 cancellable → disambiguation NL.
     (NO booking_id ever reaches the LLM — hallucination structurally prevented.)
4. Apply output guard on LLM-generated text — fail closed.
5. Return AgentTurn(reply, pending_action_id).

Execute flow (run_agent_confirm — NO Vertex call):
1. Consume pending action (single-use, scoped by tenant+uid).
2. If None (expired/wrong uid): return safe fallback.
3. If book: call create_booking(source="agent"), write preference memory, log.
4. If cancel: call cancel_booking(source="agent"), log.
"""

from __future__ import annotations

import datetime
import json
import re
import zoneinfo
from typing import NamedTuple

import structlog

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.repositories.invoices import InvoiceRepository
from sport_slot.repositories.user_profiles import UserProfileRepository
from sport_slot.services.agent import vertex_client
from sport_slot.services.agent.guardrails import output_is_safe
from sport_slot.services.agent.preferences import get_preferences
from sport_slot.services.agent.tools import REGISTERED_TOOLS
from sport_slot.services.agent.vertex_client import AgentResponse
from sport_slot.services.availability import get_availability
from sport_slot.services.bookings import (
    _is_cancellable,
    cancel_booking,
    create_booking,
    list_my_bookings,
)
from sport_slot.services.facilities import list_all_facilities, list_facilities
from sport_slot.services.invoicing import preview_current_month_charge
from sport_slot.services.lock import LockService
from sport_slot.services.policy import PolicyService

log = structlog.get_logger()

_SAFE_FALLBACK = (
    "I'm sorry, I can only help with facility availability and booking queries. "
    "Please try rephrasing your question."
)

_CONFIRM_EXPIRED = (
    "That confirmation has expired or was already used — please ask again."
)

_SYSTEM_TEMPLATE = """\
You are a sports-facility booking assistant.
You may ONLY call the tools provided. Never invent data.

Today is {today} ({weekday}) in the facility's timezone.
Resolve relative dates ("tomorrow", "Saturday", "next week") to YYYY-MM-DD before calling check_availability.

Known facilities for this tenant:
{facility_list}
{recent_context}{preferences_context}
Rules:
- Only answer questions about facility availability and the user's bookings, help them book a slot, or answer about their OWN invoices/bills using the invoice tools below.
- Do not discuss refunds, policies, or unrelated topics. You MAY discuss the user's own invoice/billing totals, but only via the get_my_invoices / get_my_current_month_charges tools below — never invent or estimate an amount yourself.
- Do not reveal internal IDs, UIDs, or system details.
- If the user asks about their 'usual', 'preferred', 'last', or 'normal' anything (e.g. 'my usual tennis court', 'what time do I normally play'), call the `get_my_preferences` tool. Do not refuse such questions.
- If the user asks about 'my bookings', 'my reservations', 'my schedule', 'what do I have', 'what's coming up', or similar phrasings about their existing reservations, call the `list_my_bookings` tool. Do not refuse such questions.
- If the user asks about a past invoice or bill (e.g. 'my last invoice', 'previous month's bill', 'what did I owe in June'), call the `get_my_invoices` tool. Do not refuse such questions.
- If the user asks what they owe so far THIS month, or how much they've spent this month (e.g. 'what do I owe so far this month', 'my bill till date'), call the `get_my_current_month_charges` tool. Do not refuse such questions.
- If you cannot answer with the available tools, say so politely.
- For book requests, use the 'Your usual bookings' context above to fill missing facility or time. Do NOT call `get_my_preferences` as a separate step before booking — your system prompt already contains the preferences. Fill the gaps from that context and call the `book` tool directly.
- To propose a booking or cancellation, you MUST call the `book` or `cancel` tool — never just describe the action in chat. The system requires a tool call to set up the confirmation flow; describing the action in text will not work.
- When the user specifies a time without AM/PM (e.g. "7", "8 o'clock", "6:30"), prefer the future-facing interpretation relative to the current local time. If the hour is ≤ 12, try the PM slot first if the AM slot has already passed. Always convert the resolved hour to HH:MM 24-hour format before calling check_availability or book.
- FACILITY MATCHING: Only use a facility_id that appears verbatim in the "Known facilities" list above. Never invent, guess, or derive a facility_id from a sport name, partial name, or any source other than the exact id= values listed.
- AMBIGUOUS FACILITY: If the user's message (or a stored preference) refers to a sport or facility name that matches more than one entry in the "Known facilities" list, do NOT call any tool. Instead, ask the user to choose by listing the matching facility names (e.g. "I found 3 badminton courts: Court A, Court B, Court C — which one did you mean?"). Only proceed with a tool call once the user has identified a single specific facility.
- UNRESOLVABLE FACILITY: If you cannot match the user's facility or sport reference to any entry in the "Known facilities" list, tell the user you couldn't find a matching facility and ask them to check the name. Do not call any tool.
"""


class AgentTurn(NamedTuple):
    reply: str
    pending_action_id: str | None = None
    pending_action_summary: dict | None = None


# Deterministic pre-Vertex invoice routing (agent reliability fix): confirmed
# via live reproduction that Gemini's tool-selection for the 15.6 invoice
# tools is genuinely non-deterministic — identical phrasing worked in one
# fresh session and failed in another, same system prompt both times.
# Conservative, whole-word keyword set — none of these words appear anywhere
# in the other tools' descriptions/phrasing space (book/cancel/
# check_availability/list_my_bookings/get_my_preferences use entirely
# different vocabulary), so there is no realistic collision risk. Deliberately
# narrow: invoice tools only, never generalized to any other tool.
_INVOICE_KEYWORDS = ("invoice", "invoices", "bill", "bills", "owe", "owed")
_CURRENT_MONTH_PHRASES = ("this month", "so far", "till date", "to date", "current month")


def _matches_invoice_keyword(message: str) -> bool:
    """Whole-word match only (never substring) — e.g. 'bill' must never
    match inside an unrelated word like 'billiards'."""
    lowered = message.lower()
    return any(re.search(rf"\b{re.escape(kw)}\b", lowered) for kw in _INVOICE_KEYWORDS)


def _is_current_month_phrasing(message: str) -> bool:
    lowered = message.lower()
    return any(phrase in lowered for phrase in _CURRENT_MONTH_PHRASES)


def _parse_date_hint(hint: str, today: datetime.date) -> datetime.date | None:
    """Parse a date hint: YYYY-MM-DD, 'today', 'tomorrow', or weekday name.

    Returns None if the hint cannot be resolved to a concrete date within
    the next 8 days. Never raises.
    """
    h = hint.strip().lower()
    if h == "today":
        return today
    if h == "tomorrow":
        return today + datetime.timedelta(days=1)
    try:
        return datetime.date.fromisoformat(hint.strip())
    except ValueError:
        pass
    _DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if h in _DAYS:
        target_dow = _DAYS.index(h)
        for offset in range(8):
            candidate = today + datetime.timedelta(days=offset)
            if candidate.weekday() == target_dow:
                return candidate
    return None


def _booking_sport(b: dict, facilities: list[dict]) -> str:
    """Return lowercased sport for a booking by looking up its facility."""
    fac = next((f for f in facilities if f.get("id") == b.get("facility_id")), None)
    if fac is None:
        return ""
    return (fac.get("sport") or fac.get("facility_type_id") or "").lower()


def _filter_cancel_candidates(
    bookings: list[dict],
    facilities: list[dict],
    sport: str,
    date_hint: str | None,
    now_local: datetime.datetime,
    buffer_hours: int,
) -> tuple[list[dict], list[dict]]:
    """Filter bookings by sport/date/window, then partition by cancellability.

    Returns (cancellable, too_late):
    - cancellable: confirmed, within 7-day window, correct sport, within cancel window
    - too_late: same criteria but past cancellation cutoff
    """
    fac_by_id: dict[str, dict] = {f["id"]: f for f in facilities if "id" in f}
    today = now_local.date()
    window_end = today + datetime.timedelta(days=7)
    target_date = _parse_date_hint(date_hint, today) if date_hint else None

    cancellable: list[dict] = []
    too_late: list[dict] = []

    for b in bookings:
        if b.get("status") != "confirmed":
            continue
        try:
            bdate = datetime.date.fromisoformat(b.get("date", ""))
        except ValueError:
            continue
        if not (today <= bdate <= window_end):
            continue
        fac = fac_by_id.get(b.get("facility_id", ""))
        if fac is None:
            continue
        fac_sport = (fac.get("sport") or fac.get("facility_type_id") or "").lower()
        if fac_sport != sport.lower():
            continue
        if target_date is not None and bdate != target_date:
            continue
        if _is_cancellable(b, now_local, buffer_hours):
            cancellable.append(b)
        else:
            too_late.append(b)

    return cancellable, too_late


def _match_disambig_candidate(user_msg: str, candidates: list[dict]) -> dict | None:
    """Return the single candidate whose date AND start both appear in user_msg.

    Returns None if zero or multiple candidates match (no change → fall through to Vertex).
    """
    msg_lower = user_msg.lower()
    matches = [
        c for c in candidates
        if c.get("date", "") in msg_lower and c.get("start", "") in msg_lower
    ]
    return matches[0] if len(matches) == 1 else None


def _facility_list_text(facilities: list[dict]) -> str:
    if not facilities:
        return "(no active facilities)"
    lines = [
        f"- {f.get('name', f.get('id', '?'))} "
        f"(sport={f.get('sport') or f.get('facility_type_id') or '?'}) "
        f"(id={f.get('id', '?')})"
        for f in facilities
    ]
    return "\n".join(lines)


def _valid_facility_ids(facilities: list[dict]) -> set[str]:
    return {f["id"] for f in facilities if "id" in f}


def _preferences_text(prefs: dict, facilities: list[dict]) -> str:
    """Render the user's last_booked preferences as a system-prompt section.

    Returns empty string when prefs is empty (no header, no blank lines).
    When non-empty, returns a section with a trailing newline so the template
    produces one clean blank line before the Rules block.
    """
    if not prefs:
        return ""
    fac_name_by_id = {f["id"]: f.get("name", f["id"]) for f in facilities if "id" in f}
    lines = ["Your usual bookings (from prior history):"]
    for sport, p in prefs.items():
        fac_id = p.get("facility_id", "?")
        fac_name = fac_name_by_id.get(fac_id, fac_id)
        start = p.get("start_time", "?")
        lines.append(f"- {sport}: {fac_name} at {start}")
    return "\n".join(lines) + "\n"


def _recent_context_text(rc: dict | None) -> str:
    """Render the previous turn (user + agent) as a system-prompt section.

    Returns empty string when rc is None/empty; otherwise a block with trailing
    newline so it flows cleanly before the preferences or Rules section.
    """
    if not rc:
        return ""
    prev_user = (rc.get("previous_user_message") or "").strip()
    prev_agent = (rc.get("previous_agent_reply") or "").strip()
    if not prev_user and not prev_agent:
        return ""
    return (
        "Recent conversation (your previous turn with the user):\n"
        f"User: {prev_user}\n"
        f"You: {prev_agent}\n\n"
    )


async def run_agent(
    ctx: TenantContext,
    client,
    store,  # PendingActionStore
    user_message: str,
    recent_context: dict | None = None,
) -> AgentTurn:
    """Execute one propose turn. Returns AgentTurn(reply, pending_action_id). Never raises."""
    try:
        facilities = list_facilities(ctx, client)

        tz_name = PolicyService(ctx, client).tenant_timezone()
        tz = zoneinfo.ZoneInfo(tz_name)
        today_local = datetime.datetime.now(tz).date()

        prefs = get_preferences(ctx, client)
        system_instruction = _SYSTEM_TEMPLATE.format(
            facility_list=_facility_list_text(facilities),
            today=today_local.isoformat(),
            weekday=today_local.strftime("%A"),
            recent_context=_recent_context_text(recent_context),
            preferences_context=_preferences_text(prefs, facilities),
        )
        valid_ids = _valid_facility_ids(facilities)

        # --- Pre-Vertex: resolve pending cancel disambiguation ---
        try:
            disambig = await store.get_latest_for_user(ctx, "cancel_disambiguation")
            if disambig is not None:
                disambig_action_id, disambig_data = disambig
                d_params = disambig_data.get("params", {})
                candidates = d_params.get("candidates", [])
                d_sport = d_params.get("sport", "")
                matched = _match_disambig_candidate(user_message, candidates)
                if matched is not None:
                    await store.consume(ctx, disambig_action_id)
                    booking_id = matched["id"]
                    fac_id = matched.get("facility_id", "")
                    fac = next((f for f in facilities if f.get("id") == fac_id), None)
                    fac_name = fac.get("name", fac_id) if fac else fac_id
                    fac_sport = (
                        (fac.get("sport") or fac.get("facility_type_id") or "") if fac else ""
                    )
                    date_str = matched.get("date", "")
                    start = matched.get("start", "")
                    try:
                        action_id = await store.propose(
                            ctx, "cancel", {"booking_id": booking_id}
                        )
                    except Exception as exc:
                        log.warning("agent_disambig_propose_error", error=str(exc))
                        return AgentTurn(
                            reply=(
                                "I couldn't prepare that cancellation right now. "
                                "Please try again."
                            )
                        )
                    summary: dict = {
                        "action_type": "cancel",
                        "booking_id": booking_id,
                        "facility_name": fac_name,
                        "sport": fac_sport,
                        "date": date_str,
                        "start": start,
                        "end": matched.get("end", ""),
                    }
                    return AgentTurn(
                        reply=(
                            f"Cancel your {d_sport} booking at {fac_name} on {date_str} "
                            f"at {start} — are you sure? Reply with confirm to proceed."
                        ),
                        pending_action_id=action_id,
                        pending_action_summary=summary,
                    )
        except Exception as exc:
            log.warning("agent_disambig_check_error", error=str(exc))
            # fall through to normal Vertex turn

        # --- Pre-Vertex: deterministic invoice-keyword routing (reliability fix) ---
        # Skips Vertex ENTIRELY for both turns on a high-confidence match — no
        # tool-selection call, no reply-phrasing call. A Vertex call to merely
        # phrase the reply would reintroduce the exact non-determinism being
        # fixed here. Any non-matching message falls through unchanged below.
        try:
            if _matches_invoice_keyword(user_message):
                tool_name = (
                    "get_my_current_month_charges"
                    if _is_current_month_phrasing(user_message)
                    else "get_my_invoices"
                )
                reply_text = _dispatch_readonly(
                    ctx, client, tool_name, {}, valid_ids, facilities, today_local
                )
                is_error = False
                try:
                    parsed = json.loads(reply_text)
                    is_error = isinstance(parsed, dict) and "error" in parsed
                except (json.JSONDecodeError, TypeError):
                    pass
                if is_error:
                    log.warning("agent_deterministic_invoice_dispatch_error", tool_name=tool_name)
                    return AgentTurn(reply=_SAFE_FALLBACK)
                log.info("agent_deterministic_invoice_routing", tool_name=tool_name)
                return AgentTurn(reply=reply_text)
        except Exception as exc:
            log.warning("agent_deterministic_invoice_routing_error", error=str(exc))
            # fall through to normal Vertex turn

        # --- Turn 1: LLM decides whether to call a tool or reply directly ---
        first: AgentResponse = await vertex_client.generate(
            message=user_message,
            system_instruction=system_instruction,
            tool_schemas=REGISTERED_TOOLS,
        )

        if first.function_call is None and first.text is None:
            log.warning("agent_turn1_empty_response")
            return AgentTurn(reply=_SAFE_FALLBACK)

        if first.function_call is not None:
            tool_name, args = first.function_call

            if tool_name == "book":
                # Propose path: deterministic text, no Turn 2, no output guard
                reply_text, pending_id, summary = await _dispatch_book(
                    ctx, client, store, args, valid_ids, facilities
                )
                return AgentTurn(
                    reply=reply_text,
                    pending_action_id=pending_id,
                    pending_action_summary=summary,
                )

            if tool_name == "cancel":
                # Propose path: deterministic Python filter, no Turn 2, no output guard
                reply_text, pending_id, summary = await _dispatch_cancel(
                    ctx, client, store, args, facilities
                )
                return AgentTurn(
                    reply=reply_text,
                    pending_action_id=pending_id,
                    pending_action_summary=summary,
                )

            # Read-only tools: dispatch → Turn 2 → output guard
            tool_result_text = _dispatch_readonly(
                ctx, client, tool_name, args, valid_ids, facilities, today_local
            )

            tool_result_content = (
                f"AUTHORITATIVE system data retrieved to answer the user's question.\n"
                f"Tool: {tool_name}\n"
                f"Data:\n{tool_result_text}\n\n"
                f"User question: {user_message}\n\n"
                f"Answer accurately from the data above. "
                f"Do not say the data is unavailable — it is provided above.\n"
                f"If the data includes a 'User's usual ... slot' line, mention it "
                f"naturally only when it adds value to the answer; do not restate it robotically."
            )
            second: AgentResponse = await vertex_client.generate(
                message=tool_result_content,
                system_instruction=system_instruction,
                tool_schemas=None,
            )

            if second.text is None:
                log.warning("agent_turn2_no_text")
                return AgentTurn(reply=_SAFE_FALLBACK)
            reply = second.text
        else:
            reply = first.text  # type: ignore[assignment]

        # --- Output guard (LLM-generated text only) ---
        safe = await output_is_safe(reply)
        if not safe:
            log.warning("agent_reply_blocked_by_guard")
            return AgentTurn(reply=_SAFE_FALLBACK)

        return AgentTurn(reply=reply)

    except Exception as exc:
        log.warning("agent_orchestrator_error", error=str(exc))
        return AgentTurn(reply=_SAFE_FALLBACK)


async def run_agent_confirm(
    ctx: TenantContext,
    client,
    lock: LockService,
    store,  # PendingActionStore
    pending_action_id: str,
) -> str:
    """Execute the confirm turn — consumes the pending action and runs create_booking.

    NO Vertex call. Params are taken verbatim from the consumed pending action.
    Never raises.
    """
    try:
        action = await store.consume(ctx, pending_action_id)
        if action is None:
            return _CONFIRM_EXPIRED

        if action.get("action_type") == "book":
            params = action["params"]
            facility_id = params["facility_id"]
            date = params["date"]
            start = params["start"]

            try:
                await create_booking(
                    ctx, client, lock,
                    facility_id, date, start,
                    source="agent",
                )
            except ApiError as exc:
                # Resolve facility for context-aware error messages (best-effort)
                try:
                    _fac = FacilityRepository(ctx, client).get(facility_id)
                except Exception:
                    _fac = None
                _fac_name = (_fac.get("name", facility_id) if _fac else facility_id)
                _sport = ((_fac.get("sport") or _fac.get("facility_type_id") or "") if _fac else "")

                if exc.code == error_codes.SLOT_CONTENDED:
                    return (
                        "That slot was just taken — would you like me to check "
                        "other available times?"
                    )
                if exc.code == error_codes.BOOKING_QUOTA_EXCEEDED:
                    if _sport:
                        return f"You've reached your daily booking limit for {_sport}."
                    return "You've reached your daily booking limit."
                if exc.code == error_codes.ALREADY_BOOKED:
                    return f"{_fac_name} on {date} at {start} is already booked."
                if exc.code == error_codes.LOCK_UNAVAILABLE:
                    return (
                        "Booking is temporarily unavailable — please try again in a moment."
                    )
                if exc.code == error_codes.SLOT_NOT_BOOKABLE:
                    return f"That slot ({start} on {date}) can't be booked right now."
                if exc.code == error_codes.FACILITY_NOT_FOUND:
                    return "I couldn't find that facility."
                if exc.code == error_codes.INVALID_DATE:
                    return "That date didn't look right — please check and try again."
                log.warning("agent_book_unknown_error", code=exc.code, status=exc.status_code)
                return "Something went wrong with that booking. Please try again."

            # Best-effort preference memory write
            try:
                _write_preference_memory(ctx, client, facility_id, start)
            except Exception as pref_exc:
                log.warning("agent_preference_write_failed", error=str(pref_exc))

            log.info(
                "agent_booking_created",
                facility_id=facility_id,
                date=date,
                start=start,
            )

            try:
                fac = FacilityRepository(ctx, client).get(facility_id)
                fac_name = fac.get("name", facility_id) if fac else facility_id
            except Exception:
                fac_name = facility_id

            return f"Booked {fac_name} on {date} at {start}."

        if action.get("action_type") == "cancel":
            params = action["params"]
            booking_id = params["booking_id"]

            try:
                result = cancel_booking(ctx, client, booking_id, source="agent")
            except ApiError as exc:
                if exc.status_code == 409:
                    return "That booking was already cancelled."
                if exc.status_code == 422:
                    return (
                        "It's too late to cancel that booking — "
                        "the cancellation window has passed."
                    )
                if exc.status_code == 404:
                    return "I couldn't find that booking — it may have already been cancelled."
                return "I wasn't able to cancel that booking. Please try again."

            log.info("agent_booking_cancelled", booking_id=booking_id)

            facility_id = result.get("facility_id", "")
            date = result.get("date", "")
            start = result.get("start", "")
            try:
                fac = FacilityRepository(ctx, client).get(facility_id)
                fac_name = fac.get("name", facility_id) if fac else facility_id
            except Exception:
                fac_name = facility_id

            return f"Cancelled your {fac_name} booking on {date} at {start}."

        log.warning("agent_unknown_pending_action_type",
                    action_type=action.get("action_type"))
        return "I'm sorry, I couldn't process that action. Please ask again."

    except Exception as exc:
        log.warning("agent_confirm_error", error=str(exc))
        return _SAFE_FALLBACK


def _write_preference_memory(
    ctx: TenantContext, client, facility_id: str, start_time: str
) -> None:
    """Partial-merge user preference: preferences.last_booked[sport] = {facility_id, start_time}."""
    fac = FacilityRepository(ctx, client).get(facility_id)
    if not fac:
        return
    sport = fac.get("sport") or fac.get("facility_type_id") or "general"
    UserProfileRepository(ctx, client).update(
        ctx.uid,
        {f"preferences.last_booked.{sport}": {"facility_id": facility_id, "start_time": start_time}},
    )


async def _dispatch_book(
    ctx: TenantContext,
    client,
    store,
    args: dict,
    valid_ids: set[str],
    facilities: list[dict],
) -> tuple[str, str | None, dict | None]:
    """Handle the 'book' tool call on the propose turn.

    Returns (nl_text, pending_action_id | None, summary | None).
    No mutation and no summary on any guard-fail or error path.
    """
    facility_id = args.get("facility_id", "")
    date_str = args.get("date", "")
    start = args.get("start", "")

    # Hallucination guard
    if facility_id not in valid_ids:
        log.warning("agent_hallucinated_facility_id_book", facility_id=facility_id)
        return (
            "I couldn't find that facility. "
            "Please check the facility name and try again.",
            None,
            None,
        )

    # AM-past → PM guard: if the AM slot on the requested date is already past, advance to PM
    try:
        _tz_name = PolicyService(ctx, client).tenant_timezone()
        _tz = zoneinfo.ZoneInfo(_tz_name)
        _now_local = datetime.datetime.now(_tz)
        _time_parts = start.split(":")
        _hour_int = int(_time_parts[0])
        _minute = _time_parts[1] if len(_time_parts) > 1 else "00"
        if _hour_int < 12:
            _target_date = datetime.date.fromisoformat(date_str)
            _start_dt = datetime.datetime(
                _target_date.year, _target_date.month, _target_date.day,
                _hour_int, int(_minute), 0, tzinfo=_tz,
            )
            if _start_dt < _now_local:
                start = f"{_hour_int + 12:02d}:{_minute}"
                log.info(
                    "agent_book_am_past_advanced_to_pm",
                    original_hour=_hour_int,
                    new_start=start,
                )
    except Exception as exc:
        log.warning("agent_book_am_pm_guard_error", error=str(exc))

    # Read-validate: confirm the slot is bookable right now
    try:
        avail = get_availability(ctx, client, facility_id, date_str)
        slots = avail.get("slots", [])
        slot = next((s for s in slots if s.get("start") == start), None)
        if slot is None or not slot.get("bookable"):
            reason = slot.get("reason", "not available") if slot else "not on the schedule grid"
            return (
                f"That slot ({start} on {date_str}) isn't available: {reason}. "
                f"Would you like me to check other times?",
                None,
                None,
            )
    except Exception as exc:
        log.warning("agent_book_avail_check_error", error=str(exc))
        return (
            "I couldn't verify that slot right now. Please try again.",
            None,
            None,
        )

    # Propose-time quota check (defensive — execute-time check is also in place)
    fac = next((f for f in facilities if f.get("id") == facility_id), None)
    sport = ((fac.get("sport") or fac.get("facility_type_id") or "").lower() if fac else "")
    if sport:
        try:
            quota_limit = int(PolicyService(ctx, client).get("max_slots_per_user_per_sport_per_day"))
            user_bookings = list_my_bookings(ctx, client, limit=100).get("items", [])
            same_sport_same_day = sum(
                1 for b in user_bookings
                if b.get("status") == "confirmed"
                and b.get("date") == date_str
                and _booking_sport(b, facilities) == sport
            )
            if same_sport_same_day >= quota_limit:
                log.info(
                    "agent_book_propose_quota_exceeded",
                    sport=sport, date=date_str, count=same_sport_same_day,
                )
                return (
                    f"You've reached your daily booking limit for {sport} on {date_str}.",
                    None,
                    None,
                )
        except Exception as exc:
            log.warning("agent_book_propose_quota_check_error", error=str(exc))
            # fall through — execute-time check is the safety net

    # Write pending action
    try:
        action_id = await store.propose(
            ctx, "book",
            {"facility_id": facility_id, "date": date_str, "start": start},
        )
    except Exception as exc:
        log.warning("agent_pending_action_propose_error", error=str(exc))
        return ("I couldn't prepare that booking right now. Please try again.", None, None)

    fac_name = fac.get("name", facility_id) if fac else facility_id
    sport_display = (fac.get("sport") or fac.get("facility_type_id") or "") if fac else ""

    summary: dict = {
        "action_type": "book",
        "facility_id": facility_id,
        "facility_name": fac_name,
        "sport": sport_display,
        "date": date_str,
        "start": start,
        "end": slot["end"],  # slot verified bookable above
    }
    return (
        f"Book {fac_name} on {date_str} at {start} — is that right? "
        f"Reply with confirm to proceed.",
        action_id,
        summary,
    )


async def _dispatch_cancel(
    ctx: TenantContext,
    client,
    store,
    args: dict,
    facilities: list[dict],
) -> tuple[str, str | None, dict | None]:
    """Handle the 'cancel' tool call on the propose turn.

    Pure Python filter — NO booking_id ever reaches the LLM.
    (cancellable=0, too_late=0) → not-found reply.
    (cancellable=0, too_late≥1) → past-cutoff reply.
    (cancellable=1) → propose pending action.
    (cancellable≥2) → disambiguation NL list.
    """
    sport = (args.get("sport") or "").strip()
    date_hint: str | None = (args.get("date_hint") or "").strip() or None

    if not sport:
        return ("Please tell me which sport's booking you'd like to cancel.", None, None)

    try:
        lmb_result = list_my_bookings(ctx, client, limit=100)
        bookings = lmb_result.get("items", [])
    except Exception as exc:
        log.warning("agent_cancel_fetch_error", error=str(exc))
        return ("I couldn't retrieve your bookings right now. Please try again.", None, None)

    try:
        policy = PolicyService(ctx, client)
        tz = zoneinfo.ZoneInfo(policy.tenant_timezone())
        now_local = datetime.datetime.now(tz).replace(tzinfo=None)
        buffer_hours = int(policy.get("cancellation_buffer_hours"))
    except Exception as exc:
        log.warning("agent_cancel_policy_error", error=str(exc))
        return ("I couldn't retrieve policy settings right now. Please try again.", None, None)

    # Use ALL facilities (active + inactive) for sport/name lookup so that bookings
    # on deactivated courts remain cancellable.  Display (system prompt) stays active-only.
    try:
        all_facs = list_all_facilities(ctx, client)
    except Exception as exc:
        log.warning("agent_cancel_all_facs_error", error=str(exc))
        all_facs = facilities  # graceful fallback to active-only

    cancellable, too_late = _filter_cancel_candidates(
        bookings, all_facs, sport, date_hint, now_local, buffer_hours
    )
    n_can = len(cancellable)
    n_late = len(too_late)
    log.info("agent_cancel_candidates", cancellable=n_can, too_late=n_late)

    if n_can == 0 and n_late == 0:
        return (
            f"You don't have any upcoming {sport} bookings within the next 7 days "
            f"that can be cancelled.",
            None,
            None,
        )

    if n_can == 0 and n_late >= 1:
        if n_late == 1:
            candidate = too_late[0]
            fac_id = candidate.get("facility_id", "")
            fac_name = next(
                (f.get("name", fac_id) for f in all_facs if f.get("id") == fac_id),
                fac_id,
            )
            return (
                f"Your {sport} booking at {fac_name} on {candidate['date']} "
                f"at {candidate['start']} is past the cancellation cutoff. "
                f"It can no longer be cancelled.",
                None,
                None,
            )
        lines = [
            f"You have {n_late} {sport} bookings within the next 7 days, "
            f"but all are past the cancellation cutoff:"
        ]
        for b in too_late[:5]:
            fac_id = b.get("facility_id", "")
            fac_name = next(
                (f.get("name", fac_id) for f in all_facs if f.get("id") == fac_id),
                fac_id,
            )
            lines.append(f"  • {fac_name} — {b.get('date', '?')} at {b.get('start', '?')}")
        return ("\n".join(lines), None, None)

    if n_can == 1:
        candidate = cancellable[0]
        booking_id = candidate["id"]
        fac_id = candidate.get("facility_id", "")
        fac = next((f for f in all_facs if f.get("id") == fac_id), None)
        fac_name = fac.get("name", fac_id) if fac else fac_id
        fac_sport = (fac.get("sport") or fac.get("facility_type_id") or "") if fac else ""
        date_str = candidate.get("date", "")
        start = candidate.get("start", "")

        try:
            action_id = await store.propose(ctx, "cancel", {"booking_id": booking_id})
        except Exception as exc:
            log.warning("agent_pending_action_propose_error", error=str(exc))
            return ("I couldn't prepare that cancellation right now. Please try again.", None, None)

        summary: dict = {
            "action_type": "cancel",
            "booking_id": booking_id,
            "facility_name": fac_name,
            "sport": fac_sport,
            "date": date_str,
            "start": start,
            "end": candidate.get("end", ""),
        }
        return (
            f"Cancel your {sport} booking at {fac_name} on {date_str} at {start} — "
            f"are you sure? Reply with confirm to proceed.",
            action_id,
            summary,
        )

    # n_can >= 2: store disambiguation state, return list
    candidates_for_store = [
        {
            "id": b["id"],
            "facility_id": b.get("facility_id", ""),
            "date": b.get("date", ""),
            "start": b.get("start", ""),
            "end": b.get("end", ""),
        }
        for b in cancellable
    ]
    try:
        await store.propose(ctx, "cancel_disambiguation", {
            "sport": sport,
            "candidates": candidates_for_store,
        })
    except Exception as exc:
        log.warning("agent_disambig_store_error", error=str(exc))

    lines = [f"You have {n_can} upcoming {sport} bookings that can be cancelled:"]
    for i, b in enumerate(cancellable, 1):
        fac_id = b.get("facility_id", "")
        fac_name = next(
            (f.get("name", fac_id) for f in all_facs if f.get("id") == fac_id),
            fac_id,
        )
        lines.append(
            f"  {i}. {fac_name} — {b.get('date', '?')} at {b.get('start', '?')}"
        )
    lines.append("Which one would you like to cancel? Please specify the date and time.")
    return ("\n".join(lines), None, None)


def _to_rupees(paise: int | None) -> str:
    """Money shown to the user/LLM must always be ₹ rupees, never raw paise
    (Phase 15.6) — mirrors the exact conversion used throughout this phase's
    UI (paise / 100, 2 decimals, ₹ prefix)."""
    return f"₹{(paise or 0) / 100:.2f}"


def _dispatch_readonly(
    ctx: TenantContext,
    client,
    tool_name: str,
    args: dict,
    valid_ids: set[str],
    facilities: list[dict],
    today_local: datetime.date | None = None,
) -> str:
    """Dispatch read-only tools. Returns enriched text for Turn 2."""
    if tool_name == "check_availability":
        facility_id = args.get("facility_id", "")
        date_str = args.get("date", "")

        if facility_id not in valid_ids:
            log.warning("agent_hallucinated_facility_id", facility_id=facility_id)
            return json.dumps({"error": "Facility not found."})

        try:
            result = get_availability(ctx, client, facility_id, date_str)
            result_text = json.dumps(result)
        except Exception as exc:
            log.warning("agent_tool_availability_error", error=str(exc))
            return json.dumps({"error": str(exc)})

        # Preference enrichment: annotate user's usual slot status
        fac = next((f for f in facilities if f.get("id") == facility_id), None)
        sport = (
            (fac.get("sport") or fac.get("facility_type_id") or "") if fac else ""
        )
        if sport:
            prefs = get_preferences(ctx, client)
            usual = prefs.get(sport)
            if usual:
                usual_start = usual.get("start_time", "")
                slot = next(
                    (s for s in result.get("slots", []) if s.get("start") == usual_start),
                    None,
                )
                if slot is None:
                    usual_status = "OFF-GRID-TODAY"
                elif slot.get("bookable"):
                    usual_status = "BOOKABLE"
                else:
                    usual_status = f"TAKEN ({slot.get('reason', 'unavailable')})"
                result_text += (
                    f"\nUser's usual {sport} slot: {usual_start} — {usual_status}"
                )

        return result_text

    elif tool_name == "list_my_bookings":
        _today = today_local if today_local is not None else datetime.date.today()
        try:
            result = list_my_bookings(ctx, client, limit=100)
            all_items = result.get("items", [])
            # Presentation-layer filter: upcoming confirmed only.
            # The underlying service and other API consumers are unaffected.
            items = []
            for b in all_items:
                if b.get("status") != "confirmed":
                    continue
                try:
                    bdate = datetime.date.fromisoformat(b.get("date", ""))
                except ValueError:
                    continue
                if bdate >= _today:
                    items.append(b)
            count = len(items)
            log.info("agent_bookings_dispatched", count=count)
            lines = [f"total_bookings={count}"]
            for item in items:
                lines.append(
                    f"  facility={item.get('facility_id', '?')} "
                    f"date={item.get('date', '?')} "
                    f"time={item.get('start', '?')} "
                    f"status={item.get('status', '?')}"
                )
            if result.get("next_cursor"):
                lines.append("(additional bookings exist beyond this page)")
            return "\n".join(lines)
        except Exception as exc:
            log.warning("agent_tool_bookings_error", error=str(exc))
            return json.dumps({"error": str(exc)})

    elif tool_name == "get_my_preferences":
        prefs = get_preferences(ctx, client)
        log.info("agent_preferences_dispatched", count=len(prefs))
        if not prefs:
            return "user has no remembered booking preferences yet."
        lines = ["user_preferences:"]
        for sport, p in prefs.items():
            lines.append(
                f"  {sport}: facility_id={p.get('facility_id', '?')} "
                f"start_time={p.get('start_time', '?')}"
            )
        return "\n".join(lines)

    elif tool_name == "get_my_invoices":
        count = args.get("count") or 3
        try:
            items = InvoiceRepository(ctx, client).list_for_household(
                ctx.household_id, limit=count
            )
            log.info("agent_invoices_dispatched", count=len(items))
            if not items:
                return "user has no generated invoices yet."
            lines = [f"total_invoices={len(items)}"]
            for inv in items:
                lines.append(
                    f"  period={inv.get('period', '?')} "
                    f"total={_to_rupees(inv.get('total_paise'))}"
                )
            return "\n".join(lines)
        except Exception as exc:
            log.warning("agent_tool_invoices_error", error=str(exc))
            return json.dumps({"error": str(exc)})

    elif tool_name == "get_my_current_month_charges":
        try:
            preview = preview_current_month_charge(
                client, ctx, ctx.tenant_id, ctx.household_id
            )
            count = len(preview.get("line_items", []))
            log.info("agent_current_month_charges_dispatched", count=count)
            period = preview.get("period", "?")
            total = _to_rupees(preview.get("total_paise"))
            if count == 0:
                return (
                    f"No bookings charged yet for {period} (in progress) — this is a "
                    f"LIVE PREVIEW, not a final or official invoice."
                )
            return (
                f"period={period} (in progress — LIVE PREVIEW, not a final invoice) "
                f"bookings_so_far={count} total_so_far={total}"
            )
        except Exception as exc:
            log.warning("agent_tool_current_month_charges_error", error=str(exc))
            return json.dumps({"error": str(exc)})

    else:
        log.warning("agent_unknown_tool_called", tool_name=tool_name)
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
