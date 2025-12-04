#!/usr/bin/env python3
"""Fetch real Alignment Forum posts using rotating proxies"""

import asyncio
import csv
import random
from pathlib import Path
from typing import Any

import httpx

GRAPHQL_URL = "https://www.alignmentforum.org/graphql"
CSV_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"
PROXIES_FILE = Path(__file__).parent.parent / "proxies.txt"


def load_proxies() -> list[str]:
    """Load proxies from file and format for httpx"""
    proxies = []
    with PROXIES_FILE.open('r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Parse format: host:port:username:password
            parts = line.split(':')
            if len(parts) == 4:
                host, port, username, password = parts
                # Format for httpx: http://username:password@host:port
                proxy_url = f"http://{username}:{password}@{host}:{port}"
                proxies.append(proxy_url)
    return proxies


async def fetch_posts_batch(offset: int, limit: int, proxy: str) -> list[dict[str, Any]]:
    """Fetch a batch of posts using a specific proxy"""

    query = """
        query GetPosts($limit: Int!, $offset: Int!) {
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
    """

    try:
        # Use proxy via environment or direct configuration
        async with httpx.AsyncClient(
            proxy=proxy,
            timeout=30.0
        ) as client:
            response = await client.post(
                GRAPHQL_URL,
                json={
                    "query": query,
                    "variables": {"limit": limit, "offset": offset}
                },
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "MCP-AlignmentForum/0.1.0"
                }
            )

            if response.status_code == 200:
                data = response.json()
                posts = data.get("data", {}).get("posts", {}).get("results", [])
                return posts
            else:
                print(f"  Error {response.status_code} at offset {offset}")
                return []

    except Exception as e:
        print(f"  Error fetching offset {offset}: {e}")
        return []


async def fetch_all_posts_parallel(proxies: list[str], total_posts: int = 1000) -> list[dict[str, Any]]:
    """Fetch posts in parallel using multiple proxies"""

    batch_size = 50
    num_batches = (total_posts + batch_size - 1) // batch_size

    print(f"Fetching {total_posts} posts in {num_batches} batches of {batch_size} using {len(proxies)} proxies")
    print("This should be FAST!\n")

    tasks = []
    for i in range(num_batches):
        offset = i * batch_size
        proxy = proxies[i % len(proxies)]  # Rotate through proxies
        tasks.append(fetch_posts_batch(offset, batch_size, proxy))
        print(f"Queued batch {i+1}/{num_batches} (offset {offset}) with proxy {i % len(proxies) + 1}")

    print("\nFetching all batches in parallel...")
    results = await asyncio.gather(*tasks)

    # Flatten results
    all_posts = []
    for batch in results:
        all_posts.extend(batch)

    return all_posts


async def main():
    print("=" * 70)
    print("FETCHING REAL ALIGNMENT FORUM DATA WITH PROXIES")
    print("=" * 70)
    print()

    # Load proxies
    proxies = load_proxies()
    print(f"Loaded {len(proxies)} proxies from {PROXIES_FILE}")
    print()

    if not proxies:
        print("ERROR: No proxies found!")
        return

    # Shuffle proxies for better distribution
    random.shuffle(proxies)

    # Fetch posts (aiming for ~1000 posts)
    posts = await fetch_all_posts_parallel(proxies, total_posts=1000)

    if not posts:
        print("\n❌ Failed to fetch any posts")
        return

    print(f"\n✅ Successfully fetched {len(posts)} REAL posts from Alignment Forum!")

    # Convert to CSV format
    csv_data = []
    for post in posts:
        summary = post.get("contents", {}).get("plaintextDescription", "")
        # Truncate long summaries
        if len(summary) > 500:
            summary = summary[:497] + "..."

        csv_data.append({
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

    # Show sample
    print("\n📋 Sample of first 5 posts:")
    for i, post in enumerate(csv_data[:5], 1):
        print(f"\n{i}. {post['title']}")
        print(f"   ID: {post['_id']}, Slug: {post['slug']}")
        print(f"   Author: {post['author']}, Karma: {post['karma']}")
        print(f"   URL: {post['pageUrl']}")

    print("\n" + "=" * 70)
    print("SUCCESS! Real data fetched and saved!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
