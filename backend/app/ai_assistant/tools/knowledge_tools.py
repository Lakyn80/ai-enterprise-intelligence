"""Tools for AI assistant to query RAG knowledge base (optional)."""

from typing import Any


async def query_knowledge(
    knowledge_service: Any,
    query: str,
) -> dict[str, Any]:
    """Query RAG knowledge base."""
    if knowledge_service is None:
        return {
            "answer": "",
            "citations": [],
            "message": "Knowledge/RAG is disabled.",
        }
    result = await knowledge_service.query(query)
    return {
        "answer": result.get("answer", ""),
        "citations": result.get("citations", []),
    }


def get_knowledge_tools_spec() -> list[dict[str, Any]]:
    """OpenAI-compatible tools schema for knowledge."""
    return [
        {
            "type": "function",
            "function": {
                "name": "query_knowledge",
                "description": "Search internal documents for information (reports, contracts, strategies). Use when user asks about internal processes, policies, or document content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            },
        },
    ]
