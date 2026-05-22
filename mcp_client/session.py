"""
MCP Client session management.
Handles Streamable HTTP connection, sampling callback routing, and progress rendering.
"""
import logging
from contextlib import asynccontextmanager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    TextContent
)
from mcp_client.nim import call_nim, NIM_MODEL

logger = logging.getLogger("scholarsleuth.client")

MCP_SERVER_URL = "http://localhost:8000/mcp"


async def sampling_handler(context, params: CreateMessageRequestParams) -> CreateMessageResult:
    """
    MCP sampling callback. Routes LLM requests to Nvidia NIM or returns mock.
    """
    logger.info("Received LLM sampling request from the MCP server.")

    # Format messages for the OpenAI-compatible API
    messages = []
    if params.systemPrompt:
        messages.append({"role": "system", "content": params.systemPrompt})

    for msg in params.messages:
        if isinstance(msg.content, TextContent):
            text = msg.content.text
        elif hasattr(msg.content, "text"):
            text = msg.content.text
        else:
            text = str(msg.content)
        messages.append({"role": msg.role, "content": text})

    # Call NIM (returns None if no keys configured)
    result = await call_nim(
        messages,
        temperature=params.temperature if params.temperature is not None else 0.7,
        max_tokens=params.maxTokens if params.maxTokens is not None else 2048
    )

    if result is None:
        logger.error("No NIM keys configured. Cannot process sampling request.")
        raise ValueError("NIM API keys are required for LLM reasoning features.")

    return CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text=result),
        model=NIM_MODEL
    )


def get_progress_renderer(task_name: str):
    """Returns an async progress callback that renders a CLI progress bar."""
    async def progress_renderer(progress: float, total: float | None, message: str | None):
        tot = total if total is not None else 100.0
        msg = message or "Processing..."
        bar_len = 20
        filled = int(round(bar_len * progress / tot)) if tot > 0 else 0
        bar = '=' * filled + '-' * (bar_len - filled)
        percentage = (progress / tot) * 100.0 if tot > 0 else 0.0
        print(f"\r[{task_name}] [{bar}] {percentage:.1f}% - {msg}", end="", flush=True)
        if progress >= tot:
            print()
    return progress_renderer


@asynccontextmanager
async def create_session():
    """
    Create and return an MCP client session connected to the server.
    Yields (read_stream, write_stream) as an async context manager.
    This is a helper used by both the chatbot app and the test harness.
    """
    async with streamable_http_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
        yield read_stream, write_stream

