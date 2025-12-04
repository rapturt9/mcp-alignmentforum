#!/usr/bin/env python3
"""
Fetch alignment-related posts from LessWrong (same codebase as AF)

LessWrong and Alignment Forum share infrastructure. We can fetch from LW
and filter for alignment posts, or just use LW posts as they overlap heavily.
"""

import asyncio
import csv
import json
from pathlib import Path
import httpx

LESSWRONG_URL = "https://www.lesswrong.com/graphql"
CSV_OUTPUT = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"

# Keywords that indicate alignment-related content
ALIGNMENT_KEYWORDS = [
    "alignment", "ai safety", "ai risk", "existential risk", "x-risk",
    "mesa-optimi", "inner alignment", "outer alignment", "corrigibility",
    "reward hacking", "deceptive alignment", "interpretability",
    "mechanistic interpretability", "elicit", "scalable oversight",
    "iterated amplification", "debate", "value learning", "rlhf"
]


def is_alignment_related(post: dict) -> bool:
    """Check if a post is alignment-related"""
    text = f"{post.get('title', '')} {post.get('contents', {}).get('plaintextDescription', '')}".lower()
    return any(keyword in text for keyword in ALIGNMENT_KEYWORDS)


async def fetch_posts_by_view(view: str, limit: int = 50) -> list:
    """Fetch posts from LessWrong"""

    query = f"""
    {{
      posts(input: {{terms: {{view: "{view}", limit: {limit}}}}}) {{
        results {{
          _id
          slug
          title
          pageUrl
          postedAt
          baseScore
          voteCount
          commentCount
          contents {{
            wordCount
            plaintextDescription
          }}
          user {{
            displayName
            slug
          }}
        }}
      }}
    }}
    """

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                LESSWRONG_URL,
                json={"query": query},
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "MCP-AlignmentForum/0.1.0"
                }
            )

            if response.status_code == 200:
                data = response.json()
                if "errors" not in data:
                    return data.get("data", {}).get("posts", {}).get("results", [])
                else:
                    print(f"GraphQL errors: {data['errors']}")

            else:
                print(f"Status {response.status_code}: {response.text[:200]}")
            return []

    except Exception as e:
        print(f"  Exception: {type(e).__name__}: {e}")
        return []


async def main():
    print("=" * 70)
    print("FETCHING ALIGNMENT POSTS FROM LESSWRONG")
    print("=" * 70)
    print()
    print("LessWrong shares infrastructure with Alignment Forum.")
    print("Fetching from LW and filtering for alignment content...")
    print()

    all_posts = []
    seen_ids = set()

    # Fetch from different views to get a good mix
    views = [("top", 100), ("new", 100), ("recentComments", 50)]

    for view, limit in views:
        print(f"Fetching '{view}' posts (limit={limit})...", end=" ")
        posts = await fetch_posts_by_view(view, limit)

        if posts:
            # Filter for alignment-related and deduplicate
            alignment_posts = [p for p in posts if is_alignment_related(p) and p["_id"] not in seen_ids]
            for p in alignment_posts:
                seen_ids.add(p["_id"])
            all_posts.extend(alignment_posts)

            print(f"✅ {len(posts)} total, {len(alignment_posts)} alignment-related")
        else:
            print("❌ Failed")

        await asyncio.sleep(1)  # Be nice to the API

    if not all_posts:
        print("\n❌ No alignment posts found")
        return

    print()
    print("=" * 70)
    print(f"✅ Found {len(all_posts)} alignment-related posts from LessWrong!")
    print("=" * 70)
    print()

    # Convert to CSV
    csv_data = []
    for post in all_posts:
        summary = post.get("contents", {}).get("plaintextDescription", "")
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
            "commentsCount": str(post.get("commentCount", 0)),
            "postedAt": post["postedAt"],
            "wordCount": str(post.get("contents", {}).get("wordCount", 0))
        })

    # Write CSV
    CSV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["_id", "slug", "title", "summary", "pageUrl", "author",
                  "authorSlug", "karma", "voteCount", "commentsCount", "postedAt", "wordCount"]

    with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"✅ CSV saved: {CSV_OUTPUT}")
    print(f"   Size: {CSV_OUTPUT.stat().st_size / 1024:.1f} KB")
    print(f"   Posts: {len(csv_data)}")
    print()

    print("Sample of first 5 posts:")
    for i, p in enumerate(csv_data[:5], 1):
        print(f"\n{i}. {p['title']}")
        print(f"   Author: {p['author']}, Karma: {p['karma']}")
        print(f"   URL: {p['pageUrl']}")

    print()
    print("=" * 70)
    print("SUCCESS! You now have REAL alignment-related posts!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
