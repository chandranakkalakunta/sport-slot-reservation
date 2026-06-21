"""Single-turn read-only agent orchestrator (ADR-0021 §2).

Flow:
1. Build system prompt with tenant facilities (hallucination context).
2. Call Vertex (generate) — may return a function_call or text.
3. If function_call: validate facility_id (hallucination guard), dispatch service,
   build result content, call Vertex again for final reply.
4. Apply output guard (rules + LLM classifier) — fail closed.
5. Return safe text or a generic fallback.
"""

from __future__ import annotations

import json

import structlog

from sport_slot.auth.context import TenantContext
from sport_slot.services.agent import vertex_client
from sport_slot.services.agent.guardrails import output_is_safe
from sport_slot.services.agent.tools import REGISTERED_TOOLS
from sport_slot.services.agent.vertex_client import AgentResponse
from sport_slot.services.availability import get_availability
from sport_slot.services.bookings import list_my_bookings
from sport_slot.services.facilities import list_facilities

log = structlog.get_logger()

_SAFE_FALLBACK = (
    "I'm sorry, I can only help with facility availability and booking queries. "
    "Please try rephrasing your question."
)

_SYSTEM_TEMPLATE = """\
You are a read-only sports-facility booking assistant.
You may ONLY call the tools provided. Never invent data.

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
        system_instruction = _SYSTEM_TEMPLATE.format(
            facility_list=_facility_list_text(facilities)
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
                f"Tool '{tool_name}' returned:\n{tool_result_text}\n\n"
                f"Original user question: {user_message}"
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
    """Call the appropriate service function. Returns JSON string or error description."""
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
        limit_str = args.get("limit", "10")
        try:
            limit = max(1, min(int(limit_str), 20))
        except (ValueError, TypeError):
            limit = 10
        try:
            result = list_my_bookings(ctx, client, limit=limit)
            return json.dumps(result)
        except Exception as exc:
            log.warning("agent_tool_bookings_error", error=str(exc))
            return json.dumps({"error": str(exc)})

    else:
        log.warning("agent_unknown_tool_called", tool_name=tool_name)
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
