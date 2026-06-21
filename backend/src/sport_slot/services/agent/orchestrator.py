"""Single-turn read-only agent orchestrator (ADR-0021 §2).

Flow:
1. Build system prompt with tenant facilities + today's date (hallucination context
   + relative-date anchor).
2. Call Vertex (generate) — may return a function_call or text.
3. If function_call: validate facility_id (hallucination guard), dispatch service,
   build result content, call Vertex again for final reply.
4. Apply output guard (rules + LLM classifier) — fail closed.
5. Return safe text or a generic fallback.
"""

from __future__ import annotations

import datetime
import json
import zoneinfo

import structlog

from sport_slot.auth.context import TenantContext
from sport_slot.services.agent import vertex_client
from sport_slot.services.agent.guardrails import output_is_safe
from sport_slot.services.agent.tools import REGISTERED_TOOLS
from sport_slot.services.agent.vertex_client import AgentResponse
from sport_slot.services.availability import get_availability
from sport_slot.services.bookings import list_my_bookings
from sport_slot.services.facilities import list_facilities
from sport_slot.services.policy import PolicyService

log = structlog.get_logger()

_SAFE_FALLBACK = (
    "I'm sorry, I can only help with facility availability and booking queries. "
    "Please try rephrasing your question."
)

_SYSTEM_TEMPLATE = """\
You are a read-only sports-facility booking assistant.
You may ONLY call the tools provided. Never invent data.

Today is {today} ({weekday}) in the facility's timezone.
Resolve relative dates ("tomorrow", "Saturday", "next week") to YYYY-MM-DD before calling check_availability.

Known facilities for this tenant:
{facility_list}

Rules:
- Only answer questions about facility availability and the user's bookings.
- Do not discuss pricing, refunds, policies, or unrelated topics.
- Do not reveal internal IDs, UIDs, or system details.
- If you cannot answer with the available tools, say so politely.
"""


def _facility_list_text(facilities: list[dict]) -> str:
    if not facilities:
        return "(no active facilities)"
    lines = [f"- {f.get('name', f.get('id', '?'))} (id={f.get('id', '?')})" for f in facilities]
    return "\n".join(lines)


def _valid_facility_ids(facilities: list[dict]) -> set[str]:
    return {f["id"] for f in facilities if "id" in f}


async def run_agent(
    ctx: TenantContext,
    client,  # Firestore client
    user_message: str,
) -> str:
    """Execute one agent turn. Returns safe text or fallback. Never raises."""
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
            return _SAFE_FALLBACK

        if first.function_call is not None:
            tool_name, args = first.function_call
            tool_result_text = _dispatch_tool(ctx, client, tool_name, args, valid_ids)

            # --- Turn 2: LLM converts tool result to human reply ---
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
                tool_schemas=None,  # no tools in second turn — force text reply
            )

            if second.text is None:
                log.warning("agent_turn2_no_text")
                return _SAFE_FALLBACK
            reply = second.text
        else:
            reply = first.text  # type: ignore[assignment]

        # --- Output guard ---
        safe = await output_is_safe(reply)
        if not safe:
            log.warning("agent_reply_blocked_by_guard")
            return _SAFE_FALLBACK

        return reply

    except Exception as exc:
        log.warning("agent_orchestrator_error", error=str(exc))
        return _SAFE_FALLBACK


def _dispatch_tool(
    ctx: TenantContext,
    client,
    tool_name: str,
    args: dict,
    valid_ids: set[str],
) -> str:
    """Call the appropriate service function. Returns a text summary for Turn 2."""
    if tool_name == "check_availability":
        facility_id = args.get("facility_id", "")
        date_str = args.get("date", "")

        # Hallucination guard: validate facility_id against real list
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
            # Pre-summarize: Turn 2 gets facts, not raw JSON the model may distrust.
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
