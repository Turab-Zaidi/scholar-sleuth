"""
OTel metric counter definitions for the MCP server.
Imported by tool modules to increment counters on each operation.
"""
from obs import meter

search_counter = meter.create_counter(
    "scholarsleuth.search.requests",
    description="Number of academic searches performed",
    unit="1"
)

db_write_counter = meter.create_counter(
    "scholarsleuth.db.writes",
    description="Number of papers written to the SQLite library",
    unit="1"
)

tool_calls_counter = meter.create_counter(
    "scholarsleuth.tool.calls",
    description="Total number of tool calls processed",
    unit="1"
)

api_failures_counter = meter.create_counter(
    "scholarsleuth.api.failures",
    description="Count of external academic API failures",
    unit="1"
)
