#!/usr/bin/env python3
"""Fetch real Alignment Forum posts with minimal fields to avoid rate limits"""

import asyncio
import csv
import time
from pathlib import Path
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport

GRAPHQL_URL = "https://www.alignmentforum.org/graphql"
CSV_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"

async def fetch_posts_minimal():
    """Fetch posts with minimal fields to reduce bandwidth"""

    transport = HTTPXAsyncTransport(
        url=GRAPHQL_URL,
        headers={
            "User-Agent": "MCP-AlignmentForum-Bot/0.1.0 (Educational Research; Contact: github.com/rapturt9/mcp-alignmentforum)"
        },
        timeout=60
    )

    all_posts = []

    # Query with MINIMAL fields - no htmlBody which is huge
    query = gql("""
        query GetPostsMinimal($limit: Int!, $offset: Int!) {
            posts(input: {
                terms: {
                    view: "new"
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
                    contents {
                        wordCount
                        plaintextDescription
                    }
                    user {
                        displayName
                        slug
                    }
                }
            }
        }
    """)

    async with Client(
        transport=transport,
        fetch_schema_from_transport=False,
        execute_timeout=60
    ) as session:

        # Start with smaller batches
        batch_size = 50
        offset = 0
        max_posts = 200  # Fetch first 200 posts

        while offset < max_posts:
            try:
                print(f"Fetching posts {offset} to {offset + batch_size}...")

                result = await session.execute(
                    query,
                    variable_values={"limit": batch_size, "offset": offset}
                )

                posts = result.get("posts", {}).get("results", [])

                if not posts:
                    print("No more posts")
                    break

                all_posts.extend(posts)
                print(f"  Got {len(posts)} posts (total: {len(all_posts)})")

                offset += batch_size

                # Longer delay between requests
                if offset < max_posts:
                    print("Waiting 5 seconds...")
                    await asyncio.sleep(5)

            except Exception as e:
                print(f"Error: {e}")
                break

    return all_posts


async def main():
    print("=" * 70)
    print("Fetching REAL Alignment Forum Posts")
    print("=" * 70)
    print()

    # Try to fetch real data
    posts = await fetch_posts_minimal()

    if not posts:
        print("\n❌ Failed to fetch posts (likely rate limited)")
        print("You can try again later when the rate limit clears.")
        return

    print(f"\n✅ Successfully fetched {len(posts)} real posts!")

    # Convert to CSV
    csv_data = []
    for post in posts:
        csv_data.append({
            "_id": post["_id"],
            "slug": post["slug"],
            "title": post["title"],
            "summary": post.get("contents", {}).get("plaintextDescription", "")[:500],
            "pageUrl": post["pageUrl"],
            "author": post["user"]["displayName"],
            "authorSlug": post["user"]["slug"],
            "karma": str(post.get("baseScore", 0)),
            "voteCount": str(post.get("voteCount", 0)),
            "commentsCount": str(post.get("commentsCount", 0)),
            "postedAt": post["postedAt"],
            "wordCount": str(post.get("contents", {}).get("wordCount", 0))
        })

    # Write CSV
    CSV_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "_id", "slug", "title", "summary", "pageUrl", "author",
        "authorSlug", "karma", "voteCount", "commentsCount", "postedAt", "wordCount"
    ]

    with CSV_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\n✅ CSV written to: {CSV_OUTPUT_PATH}")
    print(f"   File size: {CSV_OUTPUT_PATH.stat().st_size / 1024:.2f} KB")
    print(f"   Total posts: {len(csv_data)}")
    print()
    print("Sample posts:")
    for i, post in enumerate(csv_data[:5], 1):
        print(f"{i}. {post['title']}")
        print(f"   Author: {post['author']}, Karma: {post['karma']}")


if __name__ == "__main__":
    asyncio.run(main())
