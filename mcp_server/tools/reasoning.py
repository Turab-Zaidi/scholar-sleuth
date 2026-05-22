"""
Complex reasoning MCP tools: compare_papers and build_literature_review.
Use client-side LLM sampling via MCP Context and report progress notifications.
"""
import uuid
import aiosqlite
from opentelemetry import trace
from mcp.server.fastmcp import Context
from mcp.types import SamplingMessage, TextContent
from obs import tracer, logger
from mcp_server.telemetry import tool_calls_counter
from mcp_server.db import DB_PATH
from mcp_server.tools.search import search_papers


async def compare_papers(query: str = None, paper_ids: list[str] = None, ctx: Context = None) -> str:
    """
    Compare multiple academic papers. Uses LLM reasoning (sampling) to produce a comparative report.
    Specify either a query topic to search for, or a list of specific paper IDs.
    """
    tool_calls_counter.add(1, {"tool": "compare_papers"})
    if ctx is None:
        return "Error: MCP context not available. Cannot perform sampling."

    with tracer.start_as_current_span("compare_papers_tool") as span:
        papers = []
        async with aiosqlite.connect(DB_PATH) as db:
            if paper_ids:
                placeholders = ",".join(["?"] * len(paper_ids))
                async with db.execute(
                    f"SELECT title, authors, abstract, venue, year FROM papers WHERE id IN ({placeholders})",
                    paper_ids
                ) as cursor:
                    rows = await cursor.fetchall()
                    for r in rows:
                        papers.append({
                            "title": r[0], "authors": r[1], "abstract": r[2],
                            "venue": r[3], "year": r[4]
                        })
            elif query:
                logger.info(f"Compare: Search papers first for '{query}'")
                await search_papers(query=query, limit=3, source="all")

                async with db.execute(
                    "SELECT title, authors, abstract, venue, year FROM papers ORDER BY saved_at DESC LIMIT 3"
                ) as cursor:
                    rows = await cursor.fetchall()
                    for r in rows:
                        papers.append({
                            "title": r[0], "authors": r[1], "abstract": r[2],
                            "venue": r[3], "year": r[4]
                        })

        if not papers:
            return "No papers found to compare. Please perform a search or specify valid paper IDs first."

        span.set_attribute("compare.papers_count", len(papers))

        prompt = (
            "Compare and contrast the following papers. Focus on their methodologies, key findings, "
            "similarities, differences, and how they advance the field:\n\n"
        )
        for i, p in enumerate(papers):
            prompt += (
                f"Paper {i+1}:\n"
                f"Title: {p['title']}\n"
                f"Authors: {p['authors']}\n"
                f"Venue: {p['venue']} ({p['year'] or 'N/A'})\n"
                f"Abstract: {p['abstract'] or 'No abstract available.'}\n\n"
            )

        logger.info("Requesting LLM sampling for comparison from client...")
        try:
            response = await ctx.session.create_message(
                messages=[
                    SamplingMessage(role="user", content=TextContent(type="text", text=prompt))
                ],
                system_prompt="You are an expert academic research assistant specializing in comparing scientific literature.",
                max_tokens=2048,
                temperature=0.3
            )

            synthesis_text = response.content.text if hasattr(response.content, "text") else str(response.content)
            return f"### Comparative Literature Report\n\n{synthesis_text}"
        except Exception as e:
            logger.error(f"Sampling failed: {e}")
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            return f"Comparison failed during LLM sampling: {e}"


async def build_literature_review(query: str, ctx: Context = None) -> str:
    """
    Build a comprehensive literature review on a research topic.
    Performs search, updates progress notifications, and synthesizes review via client LLM.
    """
    tool_calls_counter.add(1, {"tool": "build_literature_review"})
    if ctx is None:
        return "Error: MCP context not available. Cannot perform literature review."

    with tracer.start_as_current_span("build_literature_review_tool") as span:
        span.set_attribute("review.query", query)

        await ctx.report_progress(10.0, 100.0, "Searching academic databases (Semantic Scholar, arXiv, OpenAlex)...")
        await search_papers(query=query, limit=3, source="all")

        await ctx.report_progress(40.0, 100.0, "Retrieving and parsing paper abstracts...")
        papers = []
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT title, authors, abstract, venue, year FROM papers ORDER BY saved_at DESC LIMIT 5"
            ) as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    papers.append({
                        "title": r[0], "authors": r[1], "abstract": r[2],
                        "venue": r[3], "year": r[4]
                    })

        if not papers:
            await ctx.report_progress(100.0, 100.0, "Failed: No papers found.")
            return f"Could not find any papers related to topic: {query}"

        await ctx.report_progress(70.0, 100.0, "Generating literature synthesis via Nvidia NIM...")

        prompt = (
            f"Please write a comprehensive, publication-grade literature review on the topic: '{query}'.\n"
            "Analyze the following papers, highlighting their key contributions, methodology, "
            "limitations, and how they relate to each other:\n\n"
        )
        for i, p in enumerate(papers):
            prompt += (
                f"Paper {i+1}:\n"
                f"Title: {p['title']}\n"
                f"Authors: {p['authors']}\n"
                f"Venue: {p['venue']} ({p['year'] or 'N/A'})\n"
                f"Abstract: {p['abstract'] or 'No abstract available.'}\n\n"
            )
        prompt += (
            "Structure the review with clear sections:\n"
            "1. Introduction\n"
            "2. Methodology & Approaches\n"
            "3. Critical Synthesis\n"
            "4. Research Gaps & Future Directions\n"
        )

        try:
            response = await ctx.session.create_message(
                messages=[
                    SamplingMessage(role="user", content=TextContent(type="text", text=prompt))
                ],
                system_prompt="You are an elite academic editor writing a structured, peer-reviewed literature review.",
                max_tokens=3000,
                temperature=0.4
            )

            synthesis_text = response.content.text if hasattr(response.content, "text") else str(response.content)

            await ctx.report_progress(90.0, 100.0, "Saving literature review to database...")
            session_id = uuid.uuid4().hex
            title = f"Literature Review: {query}"

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO review_sessions (id, title, query, synthesis) VALUES (?, ?, ?, ?)",
                    (session_id, title, query, synthesis_text)
                )
                await db.commit()

            await ctx.report_progress(100.0, 100.0, "Complete!")

            return (
                f"### {title}\n"
                f"**Review Session ID**: `{session_id}`\n\n"
                f"{synthesis_text}"
            )
        except Exception as e:
            logger.error(f"Literature review synthesis failed: {e}")
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            await ctx.report_progress(100.0, 100.0, "Failed during synthesis.")
            return f"Literature review synthesis failed: {e}"
