"""
ScholarSleuth MCP Server entry point.
Registers all tools on the FastMCP instance and serves via Streamable HTTP.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP, Context
from obs import logger, instrument_fastapi_app

# Import tool implementation functions
from mcp_server.tools.search import search_papers
from mcp_server.tools.citations import analyze_citations
from mcp_server.tools.open_access import get_open_access_pdf
from mcp_server.tools.library import save_to_library, export_bibtex
from mcp_server.tools.reasoning import compare_papers, build_literature_review

# Initialize FastMCP Server
mcp = FastMCP("ScholarSleuth", host="0.0.0.0", port=8000)



@mcp.tool()
async def tool_search_papers(query: str, limit: int = 5, source: str = "all") -> str:
    """Search academic papers from multiple databases (Semantic Scholar, arXiv, OpenAlex).
    Saves results to the local SQLite database automatically."""
    return await search_papers(query, limit, source)


@mcp.tool()
async def tool_analyze_citations(paper_id: str) -> str:
    """Analyze citation metrics and timelines for a given Semantic Scholar paper ID or DOI."""
    return await analyze_citations(paper_id)


@mcp.tool()
async def tool_get_open_access_pdf(doi: str) -> str:
    """Query Unpaywall to find an open access PDF link for a given DOI."""
    return await get_open_access_pdf(doi)


@mcp.tool()
async def tool_save_to_library(
    api_key: str,
    paper_id: str,
    title: str,
    authors: str = "",
    abstract: str = "",
    url: str = "",
    venue: str = "",
    year: int = None
) -> str:
    """Save a paper to the authenticated user's library database.
    Requires user's API Key for basic authorization."""
    return await save_to_library(api_key, paper_id, title, authors, abstract, url, venue, year)


@mcp.tool()
async def tool_export_bibtex(api_key: str) -> str:
    """Export all papers saved in the user's library in clean BibTeX format.
    Requires user's API Key for authentication."""
    return await export_bibtex(api_key)


@mcp.tool()
async def tool_compare_papers(
    query: str = None, paper_ids: list[str] = None, ctx: Context = None
) -> str:
    """Compare multiple academic papers using LLM reasoning (sampling).
    Specify either a query topic to search for, or a list of specific paper IDs."""
    return await compare_papers(query, paper_ids, ctx)


@mcp.tool()
async def tool_build_literature_review(query: str, ctx: Context = None) -> str:
    """Build a comprehensive literature review on a research topic.
    Performs search, updates progress notifications, and synthesizes review via client LLM."""
    return await build_literature_review(query, ctx)


# Build and instrument Starlette app
app = mcp.streamable_http_app()
instrument_fastapi_app(app)


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting ScholarSleuth MCP Streamable HTTP Server on http://localhost:8000/mcp")
    uvicorn.run(app, host="0.0.0.0", port=8000)
