"""Thin async Vertex AI wrapper — the ONLY file that touches google-genai.

All google imports are DEFERRED (inside function bodies) so this module is
safe to import without credentials or the SDK installed. Tests mock
`generate` and `classify_output` entirely; _get_client() is never reached.
"""

from __future__ import annotations

from typing import Any, NamedTuple

import structlog

log = structlog.get_logger()

_client: Any = None


class AgentResponse(NamedTuple):
    function_call: tuple[str, dict] | None  # (tool_name, args) or None
    text: str | None


def _get_client() -> Any:
    global _client
    if _client is None:
        from google import genai  # deferred: safe when creds absent at import
        from sport_slot.config import get_settings
        s = get_settings()
        _client = genai.Client(
            vertexai=True, project=s.vertex_project, location=s.vertex_location
        )
    return _client


def _build_tool(schema: dict) -> Any:
    """Convert a plain-dict tool schema to a google.genai types.Tool."""
    from google.genai import types
    props = {
        k: types.Schema(type=types.Type.STRING, description=v.get("description", ""))
        for k, v in schema["parameters"].get("properties", {}).items()
    }
    return types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name=schema["name"],
            description=schema.get("description", ""),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties=props,
                required=schema["parameters"].get("required", []),
            ),
        )
    ])


async def generate(
    message: str,
    system_instruction: str | None = None,
    tool_schemas: list[dict] | None = None,
) -> AgentResponse:
    """Single async Vertex call. Returns AgentResponse (function_call XOR text)."""
    from google.genai import types
    from sport_slot.config import get_settings

    settings = get_settings()
    client = _get_client()

    tools = [_build_tool(s) for s in tool_schemas] if tool_schemas else None
    config_kwargs: dict[str, Any] = {}
    if system_instruction:
        config_kwargs["system_instruction"] = [system_instruction]
    if tools:
        config_kwargs["tools"] = tools

    try:
        response = await client.aio.models.generate_content(
            model=settings.agent_model,
            contents=message,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    except Exception as exc:
        log.warning("vertex_generate_failed", error=str(exc))
        return AgentResponse(function_call=None, text=None)

    try:
        for candidate in (response.candidates or []):
            for part in (candidate.content.parts or []):
                fc = getattr(part, "function_call", None)
                if fc and getattr(fc, "name", None):
                    return AgentResponse(
                        function_call=(fc.name, dict(fc.args or {})),
                        text=None,
                    )
        return AgentResponse(function_call=None, text=response.text)
    except Exception as exc:
        log.warning("vertex_response_parse_failed", error=str(exc))
        return AgentResponse(function_call=None, text=None)


async def classify_output(reply: str) -> bool:
    """LLM safety classifier for agent output. Fail closed — returns False on any error."""
    from google.genai import types
    from sport_slot.config import get_settings

    settings = get_settings()
    client = _get_client()

    prompt = (
        "Is the following reply appropriate for a sports-facility booking assistant? "
        "It should be on-subject (availability or booking queries only), "
        "appropriately toned, and free of leaked or irrelevant data. "
        "Answer with exactly one word: yes or no.\n\nReply to assess:\n" + reply
    )
    try:
        response = await client.aio.models.generate_content(
            model=settings.agent_model,
            contents=prompt,
            config=types.GenerateContentConfig(),
        )
        answer = (response.text or "").strip().lower()
        return answer.startswith("yes")
    except Exception as exc:
        log.warning("vertex_classify_failed", error=str(exc))
        return False  # fail closed
