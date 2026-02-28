"""LangGraph-style agent workflow: tool selection -> execute -> compose answer."""

import json
from datetime import date
from typing import Any

from app.ai_assistant.providers.base import LLMProvider
from app.ai_assistant.tools.forecast_tools import (
    get_forecast,
    get_forecast_tools_spec,
    get_scenario_price_change,
)
from app.ai_assistant.tools.data_tools import get_sales_summary, get_data_tools_spec
from app.ai_assistant.tools.knowledge_tools import (
    query_knowledge,
    get_knowledge_tools_spec,
)


SYSTEM_PROMPT = """You are an AI analyst assistant for retail forecasting. You MUST base your answers ONLY on data returned by the tools you call. You must NEVER invent or guess numeric values. If the user asks for a number that is not available in tool outputs, say that you need that data and suggest which metric or tool might provide it. Be concise and data-driven."""


def _parse_tool_args(args: str) -> dict[str, Any]:
    """Parse JSON tool arguments."""
    try:
        return json.loads(args)
    except json.JSONDecodeError:
        return {}


async def execute_tool(
    name: str,
    arguments: dict[str, Any],
    forecasting_service: Any,
    forecasting_repo: Any,
    knowledge_service: Any | None,
) -> str:
    """Execute a tool by name and return result as string."""
    if name == "get_forecast":
        pid = arguments.get("product_id", "")
        fd = date.fromisoformat(arguments.get("from_date", "2024-01-01"))
        td = date.fromisoformat(arguments.get("to_date", "2024-01-31"))
        result = await get_forecast(forecasting_service, pid, fd, td)
        return json.dumps(result)

    if name == "get_scenario_price_change":
        pid = arguments.get("product_id", "")
        fd = date.fromisoformat(arguments.get("from_date", "2024-01-01"))
        td = date.fromisoformat(arguments.get("to_date", "2024-01-31"))
        delta = float(arguments.get("price_delta_pct", 0))
        result = await get_scenario_price_change(
            forecasting_service, pid, fd, td, delta
        )
        return json.dumps(result)

    if name == "get_sales_summary":
        pid = arguments.get("product_id", "")
        fd = date.fromisoformat(arguments.get("from_date", "2024-01-01"))
        td = date.fromisoformat(arguments.get("to_date", "2024-01-31"))
        result = await get_sales_summary(forecasting_repo, pid, fd, td)
        return json.dumps(result)

    if name == "query_knowledge":
        q = arguments.get("query", "")
        result = await query_knowledge(knowledge_service, q)
        return json.dumps(result)

    return json.dumps({"error": f"Unknown tool: {name}"})


async def run_agent(
    user_message: str,
    provider: LLMProvider,
    forecasting_service: Any,
    forecasting_repo: Any,
    knowledge_service: Any | None,
    rag_enabled: bool = False,
) -> tuple[str, list[str], list[dict]]:
    """
    Run the agent: user_input -> tool_selection -> tool_execute -> answer_compose.
    Returns (answer, used_tools, citations).
    """
    tools_spec = get_forecast_tools_spec() + get_data_tools_spec()
    if rag_enabled:
        tools_spec = tools_spec + get_knowledge_tools_spec()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    used_tools: list[str] = []
    citations: list[dict] = []
    max_iterations = 5

    for _ in range(max_iterations):
        response = await provider.generate(messages, tools_spec)
        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])

        if not tool_calls:
            return content.strip(), used_tools, citations

        tool_messages: list[dict] = []
        for tc in tool_calls:
            name = tc.get("name", "")
            args_str = tc.get("arguments", "{}")
            args = _parse_tool_args(args_str)
            used_tools.append(name)
            result = await execute_tool(
                name, args,
                forecasting_service, forecasting_repo, knowledge_service,
            )
            tool_messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", "unknown"),
                "content": result,
            })
            if name == "query_knowledge":
                try:
                    data = json.loads(result)
                    for c in data.get("citations", []):
                        citations.append(c)
                except Exception:
                    pass
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        messages.extend(tool_messages)

    return (
        "I've gathered the available data. Please refine your question if you need more specific information.",
        used_tools,
        citations,
    )
