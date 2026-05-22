"""
Integration test harness for ScholarSleuth MCP tools.
Connects to a running MCP server and validates all tools end-to-end.
"""
import sys
import asyncio
import logging
from mcp import ClientSession
from mcp_client.session import sampling_handler, get_progress_renderer, create_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scholarsleuth.tests")


async def run_all_tests(query: str):
    """Execute the full integration test suite against a running MCP server."""
    logger.info("Connecting to MCP SSE Server...")

    async with create_session() as (read_stream, write_stream):
        async with ClientSession(
            read_stream,
            write_stream,
            sampling_callback=sampling_handler
        ) as session:
            logger.info("Initializing MCP session...")
            await session.initialize()
            logger.info("Session initialized successfully.")

            # List available tools
            logger.info("Verifying server tools...")
            tools = await session.list_tools()
            for t in tools.tools:
                logger.info(f" - Tool: {t.name}")

            # TEST 1: SEARCH PAPERS
            print(f"\n--- TEST 1: SEARCH PAPERS (Query: '{query}', Source: 'all') ---")
            try:
                res = await session.call_tool(
                    "tool_search_papers",
                    {"query": query, "limit": 2, "source": "all"}
                )
                print(res.content[0].text)
            except Exception as e:
                logger.error(f"Search papers failed: {e}")

            # TEST 2: CITATION ANALYSIS
            target_paper = "10.1145/3358960"
            print(f"\n--- TEST 2: CITATION ANALYSIS (Paper ID: {target_paper}) ---")
            try:
                res = await session.call_tool(
                    "tool_analyze_citations",
                    {"paper_id": target_paper}
                )
                print(res.content[0].text)
            except Exception as e:
                logger.error(f"Citation analysis failed: {e}")

            # TEST 3: UNPAYWALL OPEN ACCESS PDF
            target_doi = "10.1145/3477132.3483582"
            print(f"\n--- TEST 3: UNPAYWALL OPEN ACCESS (DOI: {target_doi}) ---")
            try:
                res = await session.call_tool(
                    "tool_get_open_access_pdf",
                    {"doi": target_doi}
                )
                print(res.content[0].text)
            except Exception as e:
                logger.error(f"Unpaywall test failed: {e}")

            # TEST 4a: SAVE TO LIBRARY (Valid Key)
            valid_token = "sleuth_token_abc123"
            print(f"\n--- TEST 4a: SAVE TO LIBRARY (Valid Key: {valid_token}) ---")
            try:
                res = await session.call_tool(
                    "tool_save_to_library",
                    {
                        "api_key": valid_token,
                        "paper_id": "arxiv:2103.00020",
                        "title": "Learning Transferable Visual Models From Natural Language Supervision",
                        "authors": "Alec Radford, Jong Wook Kim, Chris Hallacy, Aditya Ramesh, Gabriel Goh, Sandhini Agarwal",
                        "abstract": "State-of-the-art computer vision systems are trained to predict a fixed set of predetermined object categories.",
                        "url": "https://arxiv.org/abs/2103.00020",
                        "venue": "arXiv preprint",
                        "year": 2021
                    }
                )
                print(res.content[0].text)
            except Exception as e:
                logger.error(f"Save with valid key failed: {e}")

            # TEST 4b: SAVE TO LIBRARY (Invalid Key)
            invalid_token = "fake_unauthorized_key"
            print(f"\n--- TEST 4b: SAVE TO LIBRARY (Invalid Key: {invalid_token}) ---")
            try:
                res = await session.call_tool(
                    "tool_save_to_library",
                    {"api_key": invalid_token, "paper_id": "arxiv:2103.00020", "title": "Unwanted Paper"}
                )
                print(res.content[0].text)
            except Exception as e:
                logger.error(f"Save with invalid key failed: {e}")

            # TEST 5: EXPORT BIBTEX
            print(f"\n--- TEST 5: EXPORT BIBTEX (Valid Key: {valid_token}) ---")
            try:
                res = await session.call_tool("tool_export_bibtex", {"api_key": valid_token})
                print(res.content[0].text)
            except Exception as e:
                logger.error(f"BibTeX export failed: {e}")

            # TEST 6: COMPARE PAPERS
            print(f"\n--- TEST 6: COMPARE PAPERS (Topic: '{query}') ---")
            try:
                res = await session.call_tool("tool_compare_papers", {"query": query})
                print(res.content[0].text)
            except Exception as e:
                logger.error(f"Compare papers failed: {e}")

            # TEST 7: BUILD LITERATURE REVIEW
            print(f"\n--- TEST 7: BUILD LITERATURE REVIEW (Topic: '{query}') ---")
            try:
                res = await session.call_tool(
                    "tool_build_literature_review",
                    {"query": query},
                    progress_callback=get_progress_renderer("LIT_REVIEW")
                )
                print("\n" + res.content[0].text)
            except Exception as e:
                logger.error(f"Literature review failed: {e}")

            print("\n=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    search_query = sys.argv[1] if len(sys.argv) > 1 else "OpenTelemetry tracing"
    asyncio.run(run_all_tests(search_query))
