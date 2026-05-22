import asyncio
import aiosqlite
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "scholarsleuth.db")

async def init_db():
    print(f"Initializing database at: {DB_PATH}")
    async with aiosqlite.connect(DB_PATH) as db:
        # Enable WAL mode for high concurrency
        await db.execute("PRAGMA journal_mode=WAL;")
        
        # 1. Papers cache table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                authors TEXT,
                abstract TEXT,
                url TEXT,
                venue TEXT,
                year INTEGER,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Review sessions (literature review builds)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS review_sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                query TEXT,
                synthesis TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. Users (authentication)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. User library (maps users → saved papers)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_library (
                user_id TEXT NOT NULL,
                paper_id TEXT NOT NULL,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, paper_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(paper_id) REFERENCES papers(id)
            )
        """)

        # Seed default user for testing
        await db.execute("""
            INSERT OR IGNORE INTO users (id, username, api_key)
            VALUES ('user_1', 'researcher', 'sleuth_token_abc123')
        """)
        await db.commit()
    print("Database initialization complete.")

if __name__ == "__main__":
    asyncio.run(init_db())
