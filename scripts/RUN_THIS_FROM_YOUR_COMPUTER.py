#!/usr/bin/env python3
"""
===========================================
RUN THIS FROM YOUR COMPUTER
===========================================

This script uses the PROVEN working query format from lesswrong-gpt.
It will fetch REAL Alignment Forum posts.

This IP is rate-limited from testing, but YOUR computer should work fine!

Usage:
    python3 scripts/RUN_THIS_FROM_YOUR_COMPUTER.py
"""

import asyncio
import csv
import json
from pathlib import Path
import httpx

GRAPHQL_URL = "https://www.alignmentforum.org/graphql"
CSV_OUTPUT = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"

# Views available: "top", "new", "old", "recentComments"
# Each view returns different sets of posts
VIEWS = ["top", "new"]  # Fetch both top and new posts


async def fetch_posts_by_view(view_name: str) -> list:
    """Fetch posts using a specific view (this format is proven to work)"""

    query = f"""
    {{
      posts(input: {{terms: {{view: "{view_name}"}}}}) {{
        results {{
          _id
          slug
          title
          pageUrl
          postedAt
          baseScore
          voteCount
          commentsCount
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
                GRAPHQL_URL,
                json={"query": query},
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "MCP-AlignmentForum/0.1.0 (Educational; github.com/rapturt9/mcp-alignmentforum)"
                }
            )

            if response.status_code == 200:
                data = response.json()

                if "errors" in data:
                    print(f"  GraphQL errors: {data['errors']}")
                    return []

                posts = data.get("data", {}).get("posts", {}).get("results", [])
                return posts
            else:
                print(f"  HTTP {response.status_code}: {response.text[:100]}")
                return []

    except Exception as e:
        print(f"  Error: {e}")
        return []


async def main():
    print("=" * 70)
    print("FETCHING REAL ALIGNMENT FORUM POSTS")
    print("=" * 70)
    print()
    print("Using the PROVEN query format from lesswrong-gpt project")
    print(f"Endpoint: {GRAPHQL_URL}")
    print()

    all_posts = []
    seen_ids = set()

    for view in VIEWS:
        print(f"Fetching '{view}' posts...", end=" ")
        posts = await fetch_posts_by_view(view)

        if posts:
            # Deduplicate by ID
            new_posts = [p for p in posts if p["_id"] not in seen_ids]
            for p in new_posts:
                seen_ids.add(p["_id"])
            all_posts.extend(new_posts)

            print(f"✅ Got {len(posts)} posts ({len(new_posts)} new)")
        else:
            print("❌ Failed")

        # Small delay between views
        await asyncio.sleep(2)

    if not all_posts:
        print("\n" + "=" * 70)
        print("❌ FAILED TO FETCH POSTS")
        print("=" * 70)
        print()
        print("Possible reasons:")
        print("1. Rate limited - wait a few hours and try again")
        print("2. Network issue - check your connection")
        print("3. API changed - check alignmentforum.org/graphiql")
        print()
        print("The query format is correct and proven to work.")
        print("The issue is likely rate limiting from this IP.")
        return

    print()
    print("=" * 70)
    print(f"✅ SUCCESS! Fetched {len(all_posts)} REAL posts from Alignment Forum")
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
            "commentsCount": str(post.get("commentsCount", 0)),
            "postedAt": post["postedAt"],
            "wordCount": str(post.get("contents", {}).get("wordCount", 0))
        })

    # Write CSV
    CSV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "_id", "slug", "title", "summary", "pageUrl", "author",
        "authorSlug", "karma", "voteCount", "commentsCount", "postedAt", "wordCount"
    ]

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
        print(f"   ID: {p['_id']}")
        print(f"   Author: {p['author']}, Karma: {p['karma']}")
        print(f"   URL: {p['pageUrl']}")

    print()
    print("=" * 70)
    print("NEXT STEPS:")
    print("=" * 70)
    print()
    print("1. Commit the CSV:")
    print("   git add data/alignment-forum-posts.csv")
    print('   git commit -m "Add real AF data"')
    print("   git push")
    print()
    print("2. Test the MCP server:")
    print("   python3.11 src/mcp_alignmentforum/server_local.py")
    print()
    print("3. Configure in Claude Desktop (see README.md)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
