"""Agent orchestrator — propose (read + book intent) and execute (confirm) paths.

ADR-0021 §2/§4, ADR-0022 §5/§8.

Propose flow (run_agent):
1. Build system prompt with tenant facilities + today's date.
2. Call Vertex (generate) — may return a function_call or text.
3. If function_call:
   - read-only (check_availability, list_my_bookings): dispatch service,
     Turn 2 for NL reply, output guard.
   - book: hallucination-guard facility_id, read-validate slot is bookable,
     write pending action, return deterministic confirm prompt + pending_action_id.
     (NO Vertex Turn 2, NO mutation on propose.)
4. Apply output guard on LLM-generated text — fail closed.
5. Return AgentTurn(reply, pending_action_id).

Execute flow (run_agent_confirm — NO Vertex call):
1. Consume pending action (single-use, scoped by tenant+uid).
2. If None (expired/wrong uid): return safe fallback.
3. If book: call create_booking(source="agent"), write preference memory, log.
"""

from __future__ import annotations

import datetime
import json
import zoneinfo
from typing import NamedTuple

import structlog

from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.repositories.facilities import FacilityRepository
from sport_slot.repositories.user_profiles import UserProfileRepository
from sport_slot.services.agent import vertex_client
from sport_slot.services.agent.guardrails import output_is_safe
from sport_slot.services.agent.tools import REGISTERED_TOOLS
from sport_slot.services.agent.vertex_client import AgentResponse
from sport_slot.services.availability import get_availability
from sport_slot.services.bookings import create_booking, list_my_bookings
from sport_slot.services.facilities import list_facilities
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

Rules:
- Only answer questions about facility availability and the user's bookings, or help them book a slot.
- Do not discuss pricing, refunds, policies, or unrelated topics.
- Do not reveal internal IDs, UIDs, or system details.
- If you cannot answer with the available tools, say so politely.
"""


class AgentTurn(NamedTuple):
    reply: str
    pending_action_id: str | None = None


def _facility_list_text(facilities: list[dict]) -> str:
    if not facilities:
        return "(no active facilities)"
    lines = [f"- {f.get('name', f.get('id', '?'))} (id={f.get('id', '?')})" for f in facilities]
    return "\n".join(lines)


def _valid_facility_ids(facilities: list[dict]) -> set[str]:
    return {f["id"] for f in facilities if "id" in f}


async def run_agent(
    ctx: TenantContext,
    client,
    store,  # PendingActionStore
    user_message: str,
) -> AgentTurn:
    """Execute one propose turn. Returns AgentTurn(reply, pending_action_id). Never raises."""
    try:
        facilities = list_facilities(ctx, client)

        tz_name = PolicyService(ctx, client).tenant_timezone()
        tz = zoneinfo.ZoneInfo(tz_name)
        today_local = datetime.datetime.now(tz).date()

        system_instruction = _SYSTEM_TEMPLATE.format(
            facility_list=_facility_list_text(facilities),
            today=today_local.isoformat(),
            weekday=today_local.strftime("%A"),
        )
        valid_ids = _valid_facility_ids(facilities)

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
                reply_text, pending_id = await _dispatch_book(
                    ctx, client, store, args, valid_ids, facilities
                )
                return AgentTurn(reply=reply_text, pending_action_id=pending_id)

            # Read-only tools: dispatch → Turn 2 → output guard
            tool_result_text = _dispatch_readonly(ctx, client, tool_name, args, valid_ids)

            tool_result_content = (
                f"AUTHORITATIVE system data retrieved to answer the user's question.\n"
                f"Tool: {tool_name}\n"
                f"Data:\n{tool_result_text}\n\n"
                f"User question: {user_message}\n\n"
                f"Answer accurately from the data above. "
                f"Do not say the data is unavailable — it is provided above."
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
                if exc.status_code == 409:
                    return (
                        "That slot was just taken — would you like me to check "
                        "other available times?"
                    )
                if exc.status_code == 422:
                    return (
                        "That slot is no longer available. "
                        "Would you like me to check other times?"
                    )
                if exc.status_code == 503:
                    return (
                        "The booking system is temporarily unavailable. "
                        "Please try again in a moment."
                    )
                return "I wasn't able to complete the booking. Please try again."

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
) -> tuple[str, str | None]:
    """Handle the 'book' tool call on the propose turn.

    Returns (nl_text, pending_action_id | None). No mutation if guard fails.
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
        )

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
            )
    except Exception as exc:
        log.warning("agent_book_avail_check_error", error=str(exc))
        return (
            "I couldn't verify that slot right now. Please try again.",
            None,
        )

    # Write pending action
    try:
        action_id = await store.propose(
            ctx, "book",
            {"facility_id": facility_id, "date": date_str, "start": start},
        )
    except Exception as exc:
        log.warning("agent_pending_action_propose_error", error=str(exc))
        return ("I couldn't prepare that booking right now. Please try again.", None)

    fac_name = next(
        (f.get("name", facility_id) for f in facilities if f.get("id") == facility_id),
        facility_id,
    )
    return (
        f"Book {fac_name} on {date_str} at {start} — is that right? "
        f"Reply with confirm to proceed.",
        action_id,
    )


def _dispatch_readonly(
    ctx: TenantContext,
    client,
    tool_name: str,
    args: dict,
    valid_ids: set[str],
) -> str:
    """Dispatch check_availability and list_my_bookings. Returns text for Turn 2."""
    if tool_name == "check_availability":
        facility_id = args.get("facility_id", "")
        date_str = args.get("date", "")

        if facility_id not in valid_ids:
            log.warning("agent_hallucinated_facility_id", facility_id=facility_id)
            return json.dumps({"error": "Facility not found."})

        try:
            result = get_availability(ctx, client, facility_id, date_str)
            return json.dumps(result)
        except Exception as exc:
            log.warning("agent_tool_availability_error", error=str(exc))
            return json.dumps({"error": str(exc)})

    elif tool_name == "list_my_bookings":
        raw = args.get("limit", 10)
        try:
            limit = max(1, min(int(raw), 20))
        except (ValueError, TypeError):
            limit = 10
        try:
            result = list_my_bookings(ctx, client, limit=limit)
            items = result.get("items", [])
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

    else:
        log.warning("agent_unknown_tool_called", tool_name=tool_name)
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
