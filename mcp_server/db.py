"""
Database helper functions for the MCP server.
Handles authentication and common query patterns.
"""
import os
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "scholarsleuth.db")


async def authenticate_user(db: aiosqlite.Connection, api_key: str) -> str | None:
    """
    Verify the user's API Key against the users table.
    Returns user_id if valid, else None.
    """
    async with db.execute("SELECT id FROM users WHERE api_key = ?", (api_key,)) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None
