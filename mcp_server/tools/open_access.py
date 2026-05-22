"""
get_open_access_pdf MCP tool.
Queries Unpaywall to find legal open-access PDF copies of papers.
"""
from mcp_server.telemetry import tool_calls_counter
from mcp_server.apis import unpaywall


async def get_open_access_pdf(doi: str) -> str:
    """
    Query Unpaywall to find an open access PDF link for a given DOI.
    """
    tool_calls_counter.add(1, {"tool": "get_open_access_pdf"})

    result = await unpaywall.find_open_access(doi)

    if "error" in result:
        return f"Could not find open access details: {result['error']}"

    if not result["is_oa"]:
        return f"Paper with DOI {doi} is not Open Access."

    if result["pdf_url"]:
        return (
            f"Open Access PDF found!\n"
            f"- **Status**: {result['oa_status'].upper()}\n"
            f"- **PDF Link**: {result['pdf_url']}\n"
            f"- **Landing Page**: {result['landing_page']}"
        )
    else:
        return (
            f"Paper is registered as Open Access ({result['oa_status']}), "
            f"but no direct PDF link was returned."
        )
