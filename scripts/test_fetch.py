#!/usr/bin/env python3
"""Test script to fetch a small number of posts from Alignment Forum"""

import asyncio
import csv
from pathlib import Path
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport


GRAPHQL_URL = "https://www.alignmentforum.org/graphql"
CSV_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"


async def main():
    """Fetch a small number of posts for testing"""

    transport = HTTPXAsyncTransport(
        url=GRAPHQL_URL,
        headers={"User-Agent": "MCP-AlignmentForum/0.1.0"},
        timeout=60
    )

    async with Client(
        transport=transport,
        fetch_schema_from_transport=False,
        execute_timeout=60
    ) as session:
        # Fetch only 10 posts for testing
        query = gql("""
            query GetPosts {
                posts(input: {
                    terms: {
                        view: "new"
                        limit: 20
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
                            username
                            displayName
                            slug
                        }
                    }
                }
            }
        """)

        print("Fetching 20 recent posts from Alignment Forum...")
        result = await session.execute(query)
        posts = result.get("posts", {}).get("results", [])

        print(f"Fetched {len(posts)} posts")

        # Convert to CSV format
        csv_data = []
        for post in posts:
            csv_data.append({
                "_id": post["_id"],
                "slug": post["slug"],
                "title": post["title"],
                "summary": post.get("contents", {}).get("plaintextDescription", "")[:200],  # First 200 chars
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

        print(f"\nCSV written to: {CSV_OUTPUT_PATH}")
        print(f"File size: {CSV_OUTPUT_PATH.stat().st_size / 1024:.2f} KB")

        # Print first few posts
        print("\nFirst 3 posts:")
        for i, post in enumerate(csv_data[:3], 1):
            print(f"\n{i}. {post['title']}")
            print(f"   Author: {post['author']}, Karma: {post['karma']}")
            print(f"   URL: {post['pageUrl']}")


if __name__ == "__main__":
    asyncio.run(main())
