"""
Library management MCP tools: save_to_library and export_bibtex.
Handles authenticated paper saving and BibTeX compilation.
"""
import aiosqlite
from opentelemetry import trace
from obs import tracer, logger
from mcp_server.telemetry import tool_calls_counter, db_write_counter
from mcp_server.db import DB_PATH, authenticate_user


async def save_to_library(
    api_key: str,
    paper_id: str,
    title: str,
    authors: str = "",
    abstract: str = "",
    url: str = "",
    venue: str = "",
    year: int = None
) -> str:
    """
    Save a paper to the authenticated user's library database.
    Requires user's API Key for basic authorization.
    """
    tool_calls_counter.add(1, {"tool": "save_to_library"})
    with tracer.start_as_current_span("save_to_library_tool") as span:
        span.set_attribute("paper.id", paper_id)

        async with aiosqlite.connect(DB_PATH) as db:
            user_id = await authenticate_user(db, api_key)
            if not user_id:
                span.set_status(trace.StatusCode.ERROR, "Unauthorized API Key")
                return "Authentication failed: Invalid API Key."

            span.set_attribute("user.id", user_id)

            await db.execute(
                """
                INSERT OR REPLACE INTO papers (id, title, authors, abstract, url, venue, year)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (paper_id, title, authors, abstract, url, venue, year)
            )
            db_write_counter.add(1)

            await db.execute(
                "INSERT OR IGNORE INTO user_library (user_id, paper_id) VALUES (?, ?)",
                (user_id, paper_id)
            )
            await db.commit()

        logger.info(f"User {user_id} saved paper {paper_id} to library.")
        return f"Successfully saved paper '{title}' (ID: `{paper_id}`) to library."


async def export_bibtex(api_key: str) -> str:
    """
    Export all papers saved in the user's library in clean BibTeX format.
    Requires user's API Key for authentication.
    """
    tool_calls_counter.add(1, {"tool": "export_bibtex"})
    with tracer.start_as_current_span("export_bibtex_tool") as span:
        async with aiosqlite.connect(DB_PATH) as db:
            user_id = await authenticate_user(db, api_key)
            if not user_id:
                span.set_status(trace.StatusCode.ERROR, "Unauthorized API Key")
                return "Authentication failed: Invalid API Key."

            span.set_attribute("user.id", user_id)

            async with db.execute(
                """
                SELECT p.id, p.title, p.authors, p.venue, p.year, p.url
                FROM papers p
                JOIN user_library ul ON p.id = ul.paper_id
                WHERE ul.user_id = ?
                """,
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return "Your library is empty. Save some papers first using save_to_library."

        bibtex_entries = []
        for row in rows:
            p_id, title, authors, venue, year, url = row

            author_names = [a.strip() for a in authors.split(",") if a.strip()]
            bibtex_authors = " and ".join(author_names) if author_names else "Unknown"

            first_author_lastname = "Unknown"
            if author_names:
                first_author_lastname = author_names[0].split(" ")[-1].strip()
                first_author_lastname = "".join(c for c in first_author_lastname if c.isalnum())

            year_val = str(year) if year else "Unknown"
            cite_key = f"{first_author_lastname.lower()}{year_val}"

            clean_title = title.replace("{", "\\{").replace("}", "\\}")
            clean_venue = venue.replace("{", "\\{").replace("}", "\\}") if venue else "N/A"

            entry = (
                f"@article{{{cite_key},\n"
                f"  author  = {{{bibtex_authors}}},\n"
                f"  title   = {{{clean_title}}},\n"
                f"  journal = {{{clean_venue}}},\n"
                f"  year    = {{{year_val}}},\n"
                f"  url     = {{{url or 'N/A'}}},\n"
                f"  note    = {{Saved via ScholarSleuth MCP (ID: {p_id})}}\n"
                f"}}"
            )
            bibtex_entries.append(entry)

        return "\n\n".join(bibtex_entries)
