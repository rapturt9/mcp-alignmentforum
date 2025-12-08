#!/usr/bin/env python3
"""Sync new Alignment Forum posts from CSV to Neon PostgreSQL.

This script is designed to run after the daily CSV update.
It finds posts that exist in the CSV but not in the database,
generates embeddings, and inserts them.

Usage:
    python scripts/sync_posts.py

Requires environment variables:
    DATABASE_URL - Neon PostgreSQL connection string
    OPENAI_API_KEY - OpenAI API key for generating embeddings
"""

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


def load_csv() -> dict[str, dict]:
    """Load posts from CSV file into a dict keyed by _id."""
    if not CSV_PATH.exists():
        print(f"Error: CSV file not found at {CSV_PATH}")
        sys.exit(1)

    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["_id"]: row for row in reader}


def parse_posted_at(date_str: str) -> datetime:
    """Parse ISO 8601 date string to datetime."""
    date_str = date_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return datetime.now()


async def generate_embedding(client: AsyncOpenAI, text: str) -> list[float]:
    """Generate embedding for a single text."""
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


async def sync_new_posts() -> None:
    """Sync new posts from CSV to database."""
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Load CSV
    csv_posts = load_csv()
    print(f"Loaded {len(csv_posts)} posts from CSV")

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)
    openai_client = AsyncOpenAI()

    try:
        # Get existing post IDs
        existing_ids = set(
            row["_id"] for row in await conn.fetch("SELECT _id FROM posts")
        )
        print(f"Found {len(existing_ids)} existing posts in database")

        # Find new posts
        new_post_ids = set(csv_posts.keys()) - existing_ids
        new_posts = [csv_posts[pid] for pid in new_post_ids]

        if not new_posts:
            print("No new posts to sync!")
            return

        print(f"Found {len(new_posts)} new posts to sync")

        # Insert new posts with embeddings
        synced = 0
        for post in new_posts:
            try:
                # Generate embedding
                text = f"{post['title']}\n\n{post.get('summary', '')}"
                embedding = await generate_embedding(openai_client, text)
                embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

                # Insert post
                await conn.execute(
                    """
                    INSERT INTO posts (
                        _id, slug, title, summary, page_url, author,
                        author_slug, karma, vote_count, comments_count, posted_at,
                        word_count, af, embedding
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
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
                    embedding_str,
                )

                synced += 1
                print(f"  Added: {post['title'][:60]}...")

                # Rate limiting
                await asyncio.sleep(0.1)

            except Exception as e:
                print(f"  Error syncing {post['_id']}: {e}")
                continue

        print(f"\nSync complete! Added {synced} new posts.")

        # Also update karma/vote counts for existing posts
        print("\nUpdating metadata for existing posts...")
        updated = 0
        for pid in existing_ids:
            if pid in csv_posts:
                post = csv_posts[pid]
                try:
                    await conn.execute(
                        """
                        UPDATE posts SET
                            karma = $2,
                            vote_count = $3,
                            comments_count = $4,
                            updated_at = NOW()
                        WHERE _id = $1
                        """,
                        post["_id"],
                        int(post.get("karma", 0) or 0),
                        int(post.get("voteCount", 0) or 0),
                        int(post.get("commentsCount", 0) or 0),
                    )
                    updated += 1
                except Exception:
                    pass

        print(f"Updated metadata for {updated} existing posts.")

    finally:
        await conn.close()


def main():
    asyncio.run(sync_new_posts())


if __name__ == "__main__":
    main()
