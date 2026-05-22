"""
Semantic Scholar API wrapper.
Handles paper search and citation graph fetching.
"""
import os
import httpx
from opentelemetry import trace
from obs import tracer, logger
from mcp_server.telemetry import api_failures_counter

S2_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
S2_HEADERS = {"User-Agent": "ScholarSleuth/1.0 (mailto:scholar.sleuth.project@gmail.com)"}

if S2_API_KEY and not S2_API_KEY.startswith("your_"):
    S2_HEADERS["x-api-key"] = S2_API_KEY


async def search(query: str, limit: int) -> list[dict]:
    """Search papers on Semantic Scholar."""
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,abstract,url,venue,year"
    }
    with tracer.start_as_current_span("semantic_scholar_api_call") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.url", url)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=S2_HEADERS, timeout=10.0)
                span.set_attribute("http.status_code", response.status_code)
                response.raise_for_status()
                data = response.json()
                papers = data.get("data", [])
                # Normalize to common format
                return [
                    {
                        "paperId": p.get("paperId", ""),
                        "title": p.get("title", "Untitled"),
                        "authors": p.get("authors", []),
                        "abstract": p.get("abstract", ""),
                        "url": p.get("url", ""),
                        "venue": p.get("venue", "Semantic Scholar"),
                        "year": p.get("year", None)
                    }
                    for p in papers
                ]
            except Exception as e:
                logger.error(f"Semantic Scholar API error: {e}")
                span.record_exception(e)
                span.set_status(trace.StatusCode.ERROR, str(e))
                api_failures_counter.add(1, {"source": "semantic_scholar"})
                return []


async def fetch_citations(paper_id: str, limit: int = 100) -> dict:
    """Fetch citation data for a paper from Semantic Scholar."""
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations"
    params = {
        "fields": "title,authors,venue,year,influenceRelation",
        "limit": limit
    }
    with tracer.start_as_current_span("s2_citations_api_call") as span:
        span.set_attribute("paper.id", paper_id)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=S2_HEADERS, timeout=10.0)
                if response.status_code == 404:
                    return {"error": f"Paper {paper_id} not found on Semantic Scholar."}
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Semantic Scholar citations API error: {e}")
                span.record_exception(e)
                span.set_status(trace.StatusCode.ERROR, str(e))
                api_failures_counter.add(1, {"source": "semantic_scholar"})
                return {"error": str(e)}
