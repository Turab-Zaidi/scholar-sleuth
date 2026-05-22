"""
arXiv API wrapper.
Runs the synchronous arxiv library inside a thread pool to avoid blocking the event loop.
"""
import asyncio
import arxiv
from opentelemetry import trace
from obs import tracer, logger
from mcp_server.telemetry import api_failures_counter


def _sync_search(query: str, limit: int) -> list[dict]:
    """Synchronous arXiv search (runs inside asyncio.to_thread)."""
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=limit,
        sort_by=arxiv.SortCriterion.Relevance
    )
    results = []
    for r in client.results(search):
        paper_id = r.entry_id.split("/abs/")[-1].split("v")[0]
        results.append({
            "paperId": f"arxiv:{paper_id}",
            "title": r.title,
            "authors": [{"name": a.name} for a in r.authors],
            "abstract": r.summary,
            "url": r.entry_id,
            "venue": "arXiv preprint",
            "year": r.published.year
        })
    return results


async def search(query: str, limit: int) -> list[dict]:
    """Async arXiv search with OTel tracing."""
    with tracer.start_as_current_span("arxiv_api_call") as span:
        span.set_attribute("search.query", query)
        span.set_attribute("search.limit", limit)
        try:
            return await asyncio.to_thread(_sync_search, query, limit)
        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            api_failures_counter.add(1, {"source": "arxiv"})
            return []
