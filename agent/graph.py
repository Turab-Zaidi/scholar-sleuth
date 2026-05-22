"""
LangGraph agent definition for ScholarSleuth.
Uses a ReAct (Reasoning + Acting) loop:  Agent -> Should Continue? -> Tools -> Agent ...
"""
import os
import logging
from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

from agent.mcp_bridge import execute_mcp_tools

load_dotenv()
logger = logging.getLogger("scholarsleuth.agent")

# ── LLM Config ──────────────────────────────────────────────────────
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
ORCHESTRATOR_MODEL = "openai/gpt-oss-120b"   # Fast router
SYNTHESIZER_MODEL = "openai/gpt-oss-120b"    # Heavy (used via MCP sampling)


# ── Agent State ─────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ── System Prompt ───────────────────────────────────────────────────
SYSTEM_PROMPT = """You are **ScholarSleuth**, an elite AI-powered academic research assistant.

## Your Capabilities (MCP Tools)
1. **tool_search_papers** – Search across arXiv, Semantic Scholar, and OpenAlex.
2. **tool_analyze_citations** – Get citation metrics, influence analysis, and timelines for a paper.
3. **tool_get_open_access_pdf** – Find free legal PDFs via Unpaywall for a DOI.
4. **tool_save_to_library** – Save a paper to the user's personal library (needs their library token as `api_key`).
5. **tool_export_bibtex** – Export all saved library papers as BibTeX (needs `api_key`).
6. **tool_compare_papers** – AI-powered comparative analysis of multiple papers.
7. **tool_build_literature_review** – Generate a comprehensive literature review on a topic.

## Guidelines
- Always search before comparing or building a literature review.
- When the user references "the first paper" or "paper 2", map it to the paper ID from your earlier search results.
- Use markdown formatting for clear, readable responses.
- If a library operation requires `api_key` and the user hasn't provided one, ask for it politely.
- Be concise in conversational replies but thorough when presenting research findings.
{library_token_instruction}"""


def _build_system_prompt(library_token: str | None = None) -> str:
    """Inject the library token into the system prompt if available."""
    instruction = ""
    if library_token:
        instruction = (
            f"\n\nThe user's library token is: `{library_token}`. "
            "Use this automatically as the `api_key` argument when calling "
            "tool_save_to_library or tool_export_bibtex."
        )
    return SYSTEM_PROMPT.format(library_token_instruction=instruction)


# ── Graph Construction ──────────────────────────────────────────────
def create_agent_graph(
    tool_schemas: list[dict],
    library_token: str | None = None,
):
    """
    Build and compile the LangGraph ReAct agent.

    Parameters
    ----------
    tool_schemas : list[dict]
        OpenAI-format tool definitions fetched from the MCP server.
    library_token : str | None
        Optional user library token to inject into the system prompt.

    Returns
    -------
    Compiled LangGraph runnable with in-memory checkpointing.
    """
    # Pick the first available NIM key for the orchestrator
    _keys_str = os.getenv("NVIDIA_API_KEYS", "")
    api_key = ""
    if _keys_str:
        api_key = [k.strip() for k in _keys_str.split(",") if k.strip()][0]
    if not api_key:
        api_key = os.getenv("NVIDIA_API_KEY", "")

    llm = ChatOpenAI(
        model=ORCHESTRATOR_MODEL,
        base_url=NIM_BASE_URL,
        api_key=api_key,
        temperature=0.1,
        max_tokens=2048,
    )
    llm_with_tools = llm.bind_tools(tool_schemas)

    system_prompt = _build_system_prompt(library_token)

    # ── Node: Agent (LLM Reasoning) ────────────────────────────────
    async def agent_node(state: AgentState):
        messages = state["messages"]
        # Ensure system prompt is always first
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    # ── Node: Tool Execution via MCP ────────────────────────────────
    async def tool_node(state: AgentState):
        last_message = state["messages"][-1]
        tool_calls = [
            {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
            for tc in last_message.tool_calls
        ]
        results = await execute_mcp_tools(tool_calls)
        return {
            "messages": [
                ToolMessage(content=r["content"], tool_call_id=r["tool_call_id"])
                for r in results
            ]
        }

    # ── Routing ─────────────────────────────────────────────────────
    def should_continue(state: AgentState):
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return END

    # ── Build Graph ─────────────────────────────────────────────────
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=MemorySaver())
