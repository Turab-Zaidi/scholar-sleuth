"""
analyze_citations MCP tool.
Fetches citation networks from Semantic Scholar and produces analysis reports.
"""
from obs import tracer, logger
from mcp_server.telemetry import tool_calls_counter
from mcp_server.apis import semantic_scholar


async def analyze_citations(paper_id: str) -> str:
    """
    Analyze citation metrics and timelines for a given Semantic Scholar paper ID or DOI.
    """
    tool_calls_counter.add(1, {"tool": "analyze_citations"})

    with tracer.start_as_current_span("analyze_citations_tool") as span:
        span.set_attribute("paper.id", paper_id)
        logger.info(f"Analyzing citations for paper: {paper_id}")

        data = await semantic_scholar.fetch_citations(paper_id)

        if "error" in data:
            return data["error"]

        citations = data.get("data", [])
        total_citations = len(citations)

        if not citations:
            return f"No citations found for paper {paper_id} on Semantic Scholar."

        influential_citations = 0
        venues = {}
        years = {}
        citing_papers = []

        for cit in citations:
            citing_paper = cit.get("citingPaper", {})
            if not citing_paper:
                continue

            is_influential = cit.get("influenceRelation") == "key"
            if is_influential:
                influential_citations += 1

            venue = citing_paper.get("venue")
            if venue:
                venues[venue] = venues.get(venue, 0) + 1

            year = citing_paper.get("year")
            if year:
                years[year] = years.get(year, 0) + 1

            authors = ", ".join(
                a.get("name", "") for a in citing_paper.get("authors", []) if a.get("name")
            )
            citing_papers.append(
                f"- **{citing_paper.get('title')}** ({year or 'N/A'})\n"
                f"  *Authors*: {authors}\n"
                f"  *Venue*: {venue or 'N/A'} {'[INFLUENTIAL]' if is_influential else ''}"
            )

        top_venues = sorted(venues.items(), key=lambda x: x[1], reverse=True)[:3]
        venues_str = ", ".join(f"{v} ({c})" for v, c in top_venues) if top_venues else "N/A"

        year_trend = sorted(years.items(), key=lambda x: x[0])
        trend_str = ", ".join(f"{yr}: {c}" for yr, c in year_trend) if year_trend else "N/A"

        summary = (
            f"=== CITATION ANALYSIS FOR: {paper_id} ===\n"
            f"- **Total Citations Analyzed**: {total_citations} (max 100)\n"
            f"- **Highly Influential Citations**: {influential_citations}\n"
            f"- **Top Citing Venues**: {venues_str}\n"
            f"- **Citation Timeline**: {trend_str}\n\n"
            f"**Recent Citing Papers**:\n" + "\n".join(citing_papers[:5])
        )
        return summary
