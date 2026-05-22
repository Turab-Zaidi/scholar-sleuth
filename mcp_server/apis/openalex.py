"""
OpenAlex API wrapper.
Includes custom logic to reconstruct abstracts from inverted indices.
"""
import httpx
from opentelemetry import trace
from obs import tracer, logger
from mcp_server.telemetry import api_failures_counter

OPENALEX_HEADERS = {
    "User-Agent": "ScholarSleuth/1.0 (mailto:scholar.sleuth.project@gmail.com)"
}


def reconstruct_abstract(inverted_index: dict) -> str:
    """Rebuild an abstract string from OpenAlex's inverted index format."""
    try:
        positions = {}
        for word, idxs in inverted_index.items():
            for idx in idxs:
                positions[idx] = word
        return " ".join(positions[i] for i in sorted(positions.keys()))
    except Exception:
        return "Error reconstructing abstract."


async def search(query: str, limit: int) -> list[dict]:
    """Search papers on OpenAlex with OTel tracing."""
    url = "https://api.openalex.org/works"
    params = {"search": query, "per_page": limit}

    with tracer.start_as_current_span("openalex_api_call") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.url", url)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, params=params, headers=OPENALEX_HEADERS, timeout=10.0
                )
                span.set_attribute("http.status_code", response.status_code)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.error(f"OpenAlex API failed: {e}")
                span.record_exception(e)
                span.set_status(trace.StatusCode.ERROR, str(e))
                api_failures_counter.add(1, {"source": "openalex"})
                return []

    results = []
    for work in data.get("results", []):
        # Extract authors
        authorships = work.get("authorships", [])
        authors_list = [
            auth.get("author", {}).get("display_name", "")
            for auth in authorships
        ]
        authors_list = [name for name in authors_list if name]

        # Reconstruct abstract
        inverted_index = work.get("abstract_inverted_index")
        abstract = reconstruct_abstract(inverted_index) if inverted_index else ""

        # Extract metadata
        year = work.get("publication_year")
        host_venue = work.get("primary_location", {}).get("source", {})
        venue = host_venue.get("display_name", "Unknown Venue") if host_venue else "Unknown Venue"

        doi = work.get("doi")
        paper_id = (
            doi.replace("https://doi.org/", "")
            if doi
            else f"openalex:{work.get('id', '').split('/')[-1]}"
        )

        results.append({
            "paperId": paper_id,
            "title": work.get("title", "Untitled"),
            "authors": [{"name": name} for name in authors_list],
            "abstract": abstract,
            "url": work.get("doi") or work.get("id"),
            "venue": venue,
            "year": year
        })
    return results
