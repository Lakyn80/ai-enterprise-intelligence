"""LangGraph-style agent workflow: tool selection -> execute -> compose answer."""

import json
from datetime import date
from typing import TYPE_CHECKING, Any

from app.ai_assistant.providers.base import LLMProvider
from app.ai_assistant.tools.forecast_tools import (
    get_forecast,
    get_forecast_tools_spec,
    get_scenario_price_change,
)
from app.ai_assistant.tools.data_tools import (
    get_sales_summary,
    get_category_sales,
    get_all_products_summary,
    get_data_tools_spec,
)
from app.ai_assistant.tools.knowledge_tools import (
    query_knowledge,
    get_knowledge_tools_spec,
)

if TYPE_CHECKING:
    from app.assistants.trace_recorder import AssistantTraceRecorder


SYSTEM_PROMPT = """You are an AI analyst assistant for retail forecasting. You MUST base your answers ONLY on data returned by the tools you call. You must NEVER invent or guess numeric values.

Available data tools:
- get_sales_summary: single product summary (use for individual product queries)
- get_category_sales: all products in a category ranked by revenue (use for category-level questions: "top products in Furniture", "which products drive Electronics revenue", etc.)
- get_all_products_summary: ALL products across ALL categories ranked by revenue (use for cross-product comparisons, overall rankings, volatility analysis)
- get_forecast: future sales forecast for a product
- get_scenario_price_change: simulate price change impact

Always use get_category_sales when asked about a specific category. Use get_all_products_summary when comparing across categories or ranking all products. Use a representative date range (e.g. last available year) when the user doesn't specify dates — pick a wide range like 2022-01-01 to 2024-12-31.

Be concise and data-driven. Present numbers in a clear, ranked format."""


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
    trace: "AssistantTraceRecorder | None" = None,
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

    if name == "get_category_sales":
        cat = arguments.get("category", "")
        fd = date.fromisoformat(arguments.get("from_date", "2022-01-01"))
        td = date.fromisoformat(arguments.get("to_date", "2024-12-31"))
        result = await get_category_sales(forecasting_repo, cat, fd, td)
        return json.dumps(result)

    if name == "get_all_products_summary":
        fd = date.fromisoformat(arguments.get("from_date", "2022-01-01"))
        td = date.fromisoformat(arguments.get("to_date", "2024-12-31"))
        result = await get_all_products_summary(forecasting_repo, fd, td)
        return json.dumps(result)

    if name == "query_knowledge":
        q = arguments.get("query", "")
        result = await query_knowledge(knowledge_service, q, trace=trace)
        return json.dumps(result)

    return json.dumps({"error": f"Unknown tool: {name}"})


async def run_agent(
    user_message: str,
    provider: LLMProvider,
    forecasting_service: Any,
    forecasting_repo: Any,
    knowledge_service: Any | None,
    rag_enabled: bool = False,
    trace: "AssistantTraceRecorder | None" = None,
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
    if trace:
        trace.add_step(
            "analyst_agent_start",
            {
                "rag_enabled": rag_enabled,
                "messages": messages,
                "tools_spec": tools_spec,
            },
        )
    used_tools: list[str] = []
    citations: list[dict] = []
    max_iterations = 5

    for iteration in range(max_iterations):
        if trace:
            trace.add_step(
                "analyst_llm_request",
                {
                    "iteration": iteration + 1,
                    "messages": messages,
                    "tools_spec": tools_spec,
                },
            )
        response = await provider.generate(messages, tools_spec)
        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])
        if trace:
            trace.add_step(
                "analyst_llm_response",
                {
                    "iteration": iteration + 1,
                    "content": content,
                    "tool_calls": tool_calls,
                },
            )

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
                forecasting_service, forecasting_repo, knowledge_service, trace=trace,
            )
            if trace:
                trace.add_step(
                    "analyst_tool_execution",
                    {
                        "iteration": iteration + 1,
                        "tool_name": name,
                        "arguments": args,
                        "result": result,
                    },
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
        # Convert to OpenAI/DeepSeek wire format before sending back to API
        api_tool_calls = [
            {
                "id": tc.get("id", "unknown"),
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": tc.get("arguments", "{}"),
                },
            }
            for tc in tool_calls
        ]
        # DeepSeek requires content=null (not "") when tool_calls are present
        messages.append({"role": "assistant", "content": content or None, "tool_calls": api_tool_calls})
        messages.extend(tool_messages)

    return (
        "I've gathered the available data. Please refine your question if you need more specific information.",
        used_tools,
        citations,
    )
