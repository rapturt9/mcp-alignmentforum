#!/usr/bin/env python3
"""Update Alignment Forum posts CSV

Fetches all posts from the Alignment Forum GraphQL API and writes to a CSV file
for use by the MCP server.

Usage:
    python scripts/update_posts.py
"""

import csv
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport


# Configuration
GRAPHQL_URL = "https://www.alignmentforum.org/graphql"
CSV_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"
USER_AGENT = "MCP-AlignmentForum/0.1.0"

# Rate limiting
GRAPHQL_DELAY = 1.0  # seconds between GraphQL requests


async def fetch_all_posts() -> list[dict[str, Any]]:
    """Fetch all posts from Alignment Forum using pagination."""
    all_posts = []
    limit = 100
    offset = 0
    has_more = True

    transport = HTTPXAsyncTransport(
        url=GRAPHQL_URL,
        headers={"User-Agent": USER_AGENT}
    )

    async with Client(
        transport=transport,
        fetch_schema_from_transport=False,
        execute_timeout=30
    ) as session:
        query = gql("""
            query GetPosts($limit: Int!, $offset: Int!) {
                posts(input: {
                    terms: {
                        view: "top"
                        limit: $limit
                        offset: $offset
                    }
                }) {
                    results {
                        _id
                        slug
                        title
                        pageUrl
                        postedAt
                        baseScore
                        voteCount
                        commentsCount
                        htmlBody
                        contents {
                            html
                            wordCount
                            plaintextDescription
                        }
                        user {
                            username
                            displayName
                            slug
                        }
                    }
                }
            }
        """)

        while has_more:
            try:
                print(f"Fetching posts {offset} to {offset + limit}...", file=sys.stderr)

                result = await session.execute(
                    query,
                    variable_values={"limit": limit, "offset": offset}
                )

                posts = result.get("posts", {}).get("results", [])

                if not posts:
                    has_more = False
                else:
                    all_posts.extend(posts)
                    offset += limit
                    print(f"  Fetched {len(posts)} posts (total: {len(all_posts)})", file=sys.stderr)

                    # Rate limiting
                    time.sleep(GRAPHQL_DELAY)

            except Exception as e:
                print(f"Error fetching posts: {e}", file=sys.stderr)
                has_more = False

    print(f"Total posts fetched: {len(all_posts)}", file=sys.stderr)
    return all_posts


def process_posts(posts: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Process posts and extract data for CSV."""
    csv_data = []

    for i, post in enumerate(posts, 1):
        print(f"Processing {i}/{len(posts)}: {post['title']}", file=sys.stderr)

        # Use plaintext description as summary
        summary = post.get("contents", {}).get("plaintextDescription", "")

        # Build CSV row
        csv_row = {
            "_id": post["_id"],
            "slug": post["slug"],
            "title": post["title"],
            "summary": summary,
            "pageUrl": post["pageUrl"],
            "author": post["user"]["displayName"],
            "authorSlug": post["user"]["slug"],
            "karma": str(post.get("baseScore", 0)),
            "voteCount": str(post.get("voteCount", 0)),
            "commentsCount": str(post.get("commentsCount", 0)),
            "postedAt": post["postedAt"],
            "wordCount": str(post.get("contents", {}).get("wordCount", 0))
        }

        csv_data.append(csv_row)

    return csv_data


def write_csv(csv_data: list[dict[str, str]]) -> None:
    """Write data to CSV file."""
    # Ensure data directory exists
    CSV_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Define CSV columns
    fieldnames = [
        "_id", "slug", "title", "summary", "pageUrl", "author",
        "authorSlug", "karma", "voteCount", "commentsCount", "postedAt", "wordCount"
    ]

    # Write CSV
    with CSV_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\nCSV file written to: {CSV_OUTPUT_PATH}", file=sys.stderr)
    print(f"Total posts: {len(csv_data)}", file=sys.stderr)
    print(f"File size: {CSV_OUTPUT_PATH.stat().st_size / 1024:.2f} KB", file=sys.stderr)


async def main() -> None:
    """Main entry point."""
    start_time = time.time()

    print("=" * 60, file=sys.stderr)
    print("Alignment Forum Posts Updater", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Start time: {datetime.now().isoformat()}", file=sys.stderr)
    print("", file=sys.stderr)

    # Fetch all posts
    posts = await fetch_all_posts()

    if not posts:
        print("Error: No posts fetched", file=sys.stderr)
        sys.exit(1)

    # Process posts
    print("\nProcessing posts...", file=sys.stderr)
    csv_data = process_posts(posts)

    # Write to CSV
    write_csv(csv_data)

    elapsed_time = time.time() - start_time
    print(f"\nCompleted in {elapsed_time:.2f} seconds", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
