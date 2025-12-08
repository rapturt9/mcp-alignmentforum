#!/usr/bin/env python3
"""Migrate Alignment Forum posts from CSV to Neon PostgreSQL with embeddings.

Usage:
    python scripts/migrate_to_neon.py [--skip-embeddings] [--batch-size N]

Requires environment variables:
    DATABASE_URL - Neon PostgreSQL connection string (use unpooled for migrations)
    OPENAI_API_KEY - OpenAI API key for generating embeddings
"""

import argparse
import asyncio
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load environment variables
load_dotenv()

# Configuration
CSV_PATH = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"
DATABASE_URL = os.environ.get("DATABASE_URL", "")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


async def create_schema(conn: asyncpg.Connection) -> None:
    """Create database schema with pgvector extension."""
    print("Creating schema...")

    # Enable pgvector extension
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Create posts table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            _id VARCHAR(24) UNIQUE NOT NULL,
            slug VARCHAR(500) NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            page_url TEXT NOT NULL,
            author VARCHAR(255) NOT NULL,
            author_slug VARCHAR(255) NOT NULL,
            karma INTEGER DEFAULT 0,
            vote_count INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            posted_at TIMESTAMP WITH TIME ZONE NOT NULL,
            word_count INTEGER DEFAULT 0,
            af BOOLEAN DEFAULT TRUE,
            embedding vector(1536),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Create indexes
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_posts_posted_at ON posts(posted_at DESC);"
    )
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_af_id ON posts(_id);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug);")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_posts_author_slug ON posts(author_slug);"
    )

    print("Schema created successfully!")


async def create_vector_index(conn: asyncpg.Connection) -> None:
    """Create IVFFlat index for vector similarity search."""
    print("Creating vector index (this may take a moment)...")

    # Check if we have enough rows for IVFFlat
    count = await conn.fetchval("SELECT COUNT(*) FROM posts WHERE embedding IS NOT NULL")

    if count < 100:
        print(f"Only {count} posts with embeddings, skipping IVFFlat index (need at least 100)")
        return

    # Calculate optimal number of lists (sqrt of total rows)
    lists = max(10, min(1000, int(count**0.5)))

    await conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_posts_embedding ON posts
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = {lists});
    """)

    print(f"Vector index created with {lists} lists!")


def load_csv() -> list[dict]:
    """Load posts from CSV file."""
    if not CSV_PATH.exists():
        print(f"Error: CSV file not found at {CSV_PATH}")
        sys.exit(1)

    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        posts = list(reader)

    print(f"Loaded {len(posts)} posts from CSV")
    return posts


def parse_posted_at(date_str: str) -> datetime:
    """Parse ISO 8601 date string to datetime."""
    # Handle various ISO formats
    date_str = date_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        # Fallback for non-standard formats
        return datetime.now()


async def generate_embeddings_batch(
    client: AsyncOpenAI, texts: list[str]
) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


async def migrate_posts(
    skip_embeddings: bool = False, batch_size: int = 100
) -> None:
    """Main migration function."""
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Load CSV data
    posts = load_csv()

    # Connect to database
    print(f"Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)

    openai_client = None
    if not skip_embeddings:
        openai_client = AsyncOpenAI()

    try:
        # Create schema
        await create_schema(conn)

        # Get existing post IDs to avoid duplicates
        existing_ids = set(
            row["_id"] for row in await conn.fetch("SELECT _id FROM posts")
        )
        new_posts = [p for p in posts if p["_id"] not in existing_ids]

        if not new_posts:
            print("No new posts to migrate!")
            return

        print(f"Migrating {len(new_posts)} new posts (skipping {len(existing_ids)} existing)...")

        # Process in batches
        for i in range(0, len(new_posts), batch_size):
            batch = new_posts[i : i + batch_size]

            # Generate embeddings for batch
            embeddings = None
            if not skip_embeddings:
                texts = [f"{p['title']}\n\n{p.get('summary', '')}" for p in batch]
                try:
                    embeddings = await generate_embeddings_batch(openai_client, texts)
                except Exception as e:
                    print(f"Warning: Failed to generate embeddings: {e}")
                    embeddings = None

            # Insert batch
            for j, post in enumerate(batch):
                embedding = None
                if embeddings and j < len(embeddings):
                    embedding = "[" + ",".join(str(x) for x in embeddings[j]) + "]"

                try:
                    await conn.execute(
                        """
                        INSERT INTO posts (
                            _id, slug, title, summary, page_url, author,
                            author_slug, karma, vote_count, comments_count, posted_at,
                            word_count, af, embedding
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        ON CONFLICT (_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            summary = EXCLUDED.summary,
                            karma = EXCLUDED.karma,
                            vote_count = EXCLUDED.vote_count,
                            comments_count = EXCLUDED.comments_count,
                            embedding = COALESCE(EXCLUDED.embedding, posts.embedding),
                            updated_at = NOW()
                        """,
                        post["_id"],
                        post["slug"],
                        post["title"],
                        post.get("summary", ""),
                        post["pageUrl"],
                        post["author"],
                        post["authorSlug"],
                        int(post.get("karma", 0) or 0),
                        int(post.get("voteCount", 0) or 0),
                        int(post.get("commentsCount", 0) or 0),
                        parse_posted_at(post["postedAt"]),
                        int(post.get("wordCount", 0) or 0),
                        post.get("af", "True") == "True",
                        embedding,
                    )
                except Exception as e:
                    print(f"Error inserting post {post['_id']}: {e}")
                    continue

            progress = min(i + batch_size, len(new_posts))
            print(f"Progress: {progress}/{len(new_posts)} posts migrated")

            # Rate limiting for OpenAI API
            if not skip_embeddings:
                await asyncio.sleep(0.5)

        # Create vector index after migration
        if not skip_embeddings:
            await create_vector_index(conn)

        # Print final stats
        total = await conn.fetchval("SELECT COUNT(*) FROM posts")
        with_embeddings = await conn.fetchval(
            "SELECT COUNT(*) FROM posts WHERE embedding IS NOT NULL"
        )
        print(f"\nMigration complete!")
        print(f"Total posts: {total}")
        print(f"Posts with embeddings: {with_embeddings}")

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate posts to Neon PostgreSQL")
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip generating embeddings (faster, but no semantic search)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of posts to process per batch (default: 100)",
    )
    args = parser.parse_args()

    asyncio.run(migrate_posts(skip_embeddings=args.skip_embeddings, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
