"""Clock tool for JARVIS — ``get_current_time``.

LLMs have no clock; without this, "what time is it?" gets a refusal. The
handler reads the local system clock at call time, so answers never go stale.
"""

from __future__ import annotations

from datetime import datetime

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

TIME_FUNCTION_NAME = "get_current_time"


def time_tool_schema() -> FunctionSchema:
    return FunctionSchema(
        name=TIME_FUNCTION_NAME,
        description=(
            "Get the current local date and time on this computer. Call this whenever "
            "the user asks what time it is, today's date, or the day of the week."
        ),
        properties={},
        required=[],
    )


def describe_now(now: datetime) -> dict[str, str]:
    """Spoken-friendly fields for ``now`` (local time, with timezone name)."""
    local = now.astimezone()
    return {
        "time": local.strftime("%I:%M %p").lstrip("0"),
        "date": local.strftime("%A, %B %d, %Y").replace(" 0", " "),
        "timezone": local.tzname() or "",
        "iso": local.isoformat(timespec="seconds"),
    }


async def _time_handler(params: FunctionCallParams) -> None:
    await params.result_callback(describe_now(datetime.now()))


def register_time_tools(llm) -> list[FunctionSchema]:
    """Wire ``get_current_time`` onto the LLM service; return its schema."""
    llm.register_function(TIME_FUNCTION_NAME, _time_handler)
    return [time_tool_schema()]
