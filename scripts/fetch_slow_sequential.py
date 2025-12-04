#!/usr/bin/env python3
"""Fetch real AF data slowly and sequentially with proxies and delays"""

import asyncio
import csv
import random
from pathlib import Path

import httpx

GRAPHQL_URL = "https://www.alignmentforum.org/graphql"
CSV_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"
PROXIES_FILE = Path(__file__).parent.parent / "proxies.txt"


def load_proxies():
    """Load proxies from file"""
    proxies = []
    with PROXIES_FILE.open('r') as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split(':')
                if len(parts) == 4:
                    host, port, username, password = parts
                    proxy_url = f"http://{username}:{password}@{host}:{port}"
                    proxies.append(proxy_url)
    return proxies


async def fetch_batch(offset, limit, proxy):
    """Fetch one batch"""
    query = """
        query GetPosts($limit: Int!, $offset: Int!) {
            posts(input: {terms: {view: "new", limit: $limit, offset: $offset}}) {
                results {
                    _id
                    slug
                    title
                    pageUrl
                    postedAt
                    baseScore
                    voteCount
                    commentsCount
                    contents { wordCount plaintextDescription }
                    user { displayName slug }
                }
            }
        }
    """

    try:
        async with httpx.AsyncClient(proxy=proxy, timeout=30.0) as client:
            response = await client.post(
                GRAPHQL_URL,
                json={"query": query, "variables": {"limit": limit, "offset": offset}},
                headers={"Content-Type": "application/json", "User-Agent": "MCP-AF/0.1"}
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("posts", {}).get("results", [])
            else:
                print(f"  ❌ Error {response.status_code}")
                return []
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:50]}")
        return []


async def main():
    print("Fetching AF data SLOWLY with rotating proxies...")
    print()

    proxies = load_proxies()
    random.shuffle(proxies)
    print(f"Loaded {len(proxies)} proxies\n")

    all_posts = []
    batch_size = 20
    num_batches = 10  # Fetch 200 posts total
    delay = 3  # 3 seconds between requests

    for i in range(num_batches):
        offset = i * batch_size
        proxy = proxies[i % len(proxies)]

        print(f"Batch {i+1}/{num_batches}: offset {offset}, proxy {i % len(proxies) + 1}...", end=" ")

        posts = await fetch_batch(offset, batch_size, proxy)

        if posts:
            all_posts.extend(posts)
            print(f"✅ Got {len(posts)} posts (total: {len(all_posts)})")
        else:
            print("❌ Failed")

        if i < num_batches - 1:
            print(f"   Waiting {delay}s...")
            await asyncio.sleep(delay)

    if not all_posts:
        print("\n❌ No posts fetched")
        return

    print(f"\n✅ Total: {len(all_posts)} REAL posts!")

    # Write CSV
    csv_data = []
    for post in all_posts:
        summary = post.get("contents", {}).get("plaintextDescription", "")[:500]
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

    CSV_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["_id", "slug", "title", "summary", "pageUrl", "author",
                  "authorSlug", "karma", "voteCount", "commentsCount", "postedAt", "wordCount"]

    with CSV_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\n✅ CSV saved: {CSV_OUTPUT_PATH}")
    print(f"   Size: {CSV_OUTPUT_PATH.stat().st_size / 1024:.1f} KB")
    print(f"   Posts: {len(csv_data)}")

    print("\nFirst 3 posts:")
    for i, p in enumerate(csv_data[:3], 1):
        print(f"{i}. {p['title'][:60]}")
        print(f"   {p['author']}, Karma: {p['karma']}")


if __name__ == "__main__":
    asyncio.run(main())
