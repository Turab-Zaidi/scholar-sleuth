"""
MCP-to-LangChain tool bridge.
Dynamically fetches tool schemas from the MCP server and provides
an executor that routes LangChain tool calls back through MCP.
"""
import json
import logging
from mcp import ClientSession
from mcp_client.session import create_session, sampling_handler

logger = logging.getLogger("scholarsleuth.agent")


async def fetch_mcp_tool_schemas() -> list[dict]:
    """
    Connect to the MCP server, list all available tools, and return
    their schemas in the OpenAI function-calling format so they can be
    bound directly to a ChatOpenAI model via `.bind_tools()`.
    """
    async with create_session() as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()

            tools = []
            for tool in result.tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema
                            if tool.inputSchema
                            else {"type": "object", "properties": {}},
                    },
                })
            logger.info(f"Fetched {len(tools)} tool schemas from MCP server.")
            return tools


async def execute_mcp_tools(tool_calls: list[dict]) -> list[dict]:
    """
    Open a fresh MCP session (with sampling handler for synthesis tools),
    execute every pending tool call, and return the results.

    Each item in `tool_calls` must have keys: id, name, args.
    Returns a list of dicts with keys: tool_call_id, content.
    """
    async with create_session() as (read_stream, write_stream):
        async with ClientSession(
            read_stream,
            write_stream,
            sampling_callback=sampling_handler,
        ) as session:
            await session.initialize()

            results = []
            for tc in tool_calls:
                try:
                    logger.info(f"Executing MCP tool: {tc['name']}")
                    result = await session.call_tool(tc["name"], tc["args"])

                    # Extract text content blocks from the MCP result
                    content = ""
                    for block in result.content:
                        if hasattr(block, "text"):
                            content += block.text
                    results.append({
                        "tool_call_id": tc["id"],
                        "content": content or "Tool returned no output.",
                    })
                except Exception as e:
                    logger.error(f"MCP tool '{tc['name']}' failed: {e}")
                    results.append({
                        "tool_call_id": tc["id"],
                        "content": f"Error executing tool: {str(e)}",
                    })
            return results
