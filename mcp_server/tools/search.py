"""
search_papers MCP tool.
Queries Semantic Scholar, arXiv, and OpenAlex in parallel and caches results to SQLite.
"""
import asyncio
import aiosqlite
from obs import tracer, logger
from mcp_server.telemetry import search_counter, tool_calls_counter, db_write_counter
from mcp_server.db import DB_PATH
from mcp_server.apis import semantic_scholar, arxiv_search, openalex


async def search_papers(query: str, limit: int = 5, source: str = "all") -> str:
    """
    Search academic papers from multiple databases (Semantic Scholar, arXiv, OpenAlex).
    Saves results to the local SQLite database automatically.
    """
    source = source.lower()
    search_counter.add(1, {"query": query, "source": source})
    tool_calls_counter.add(1, {"tool": "search_papers"})

    with tracer.start_as_current_span("search_papers_tool") as span:
        span.set_attribute("mcp.tool", "search_papers")
        span.set_attribute("search.query", query)
        span.set_attribute("search.limit", limit)
        span.set_attribute("search.source", source)

        logger.info(f"Executing search_papers with source '{source}' for query: '{query}'")

        # Build parallel tasks based on requested source
        tasks = []
        if source in ("all", "semantic_scholar", "semanticscholar"):
            tasks.append(semantic_scholar.search(query, limit))
        if source in ("all", "arxiv"):
            tasks.append(arxiv_search.search(query, limit))
        if source in ("all", "openalex"):
            tasks.append(openalex.search(query, limit))

        search_results = await asyncio.gather(*tasks)

        # Flatten all results into a single list
        papers_data = []
        for result_set in search_results:
            papers_data.extend(result_set)

        span.set_attribute("search.results_count", len(papers_data))

        # Cache to SQLite
        with tracer.start_as_current_span("sqlite_write_papers"):
            logger.info(f"Writing {len(papers_data)} results to SQLite...")
            async with aiosqlite.connect(DB_PATH) as db:
                for paper in papers_data:
                    paper_id = paper.get("paperId", "")
                    title = paper.get("title", "Untitled")
                    authors_list = paper.get("authors", [])
                    authors_str = ", ".join(
                        a.get("name", "") for a in authors_list if a.get("name")
                    )
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO papers (id, title, authors, abstract, url, venue, year)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            paper_id, title, authors_str,
                            paper.get("abstract", ""),
                            paper.get("url", ""),
                            paper.get("venue", ""),
                            paper.get("year", None)
                        )
                    )
                    db_write_counter.add(1)
                await db.commit()
            logger.info(f"Successfully cached {len(papers_data)} papers to SQLite database.")

        # Format output
        output_results = []
        for i, paper in enumerate(papers_data):
            title = paper.get("title", "Untitled")
            authors = ", ".join(a.get("name", "") for a in paper.get("authors", []))
            venue = paper.get("venue", "N/A")
            year = paper.get("year", "N/A")
            abstract = paper.get("abstract", "No abstract available.")
            paper_url = paper.get("url", "N/A")
            p_id = paper.get("paperId", "")

            output_results.append(
                f"{i+1}. **{title}** (ID: `{p_id}`)\n"
                f"   *Authors*: {authors}\n"
                f"   *Venue*: {venue} ({year})\n"
                f"   *URL*: {paper_url}\n"
                f"   *Abstract*: {abstract[:300]}...\n"
            )

        return "\n".join(output_results) if output_results else "No papers found for the query."
