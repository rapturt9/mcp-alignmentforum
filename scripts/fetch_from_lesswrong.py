#!/usr/bin/env python3
"""
Fetch Alignment Forum posts from LessWrong GraphQL API

LessWrong and Alignment Forum share infrastructure. We fetch from LW API
and use the 'af' field to filter for Alignment Forum posts only.

Usage:
  python fetch_from_lesswrong.py            # Incremental: fetch last 48 hours
  python fetch_from_lesswrong.py --full     # Full: fetch all AF posts
"""

import argparse
import asyncio
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx

LESSWRONG_URL = "https://www.lesswrong.com/graphql"
CSV_OUTPUT = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"
GRAPHQL_DELAY = 1.0  # Seconds between requests to avoid rate limiting


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Fetch Alignment Forum posts")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Fetch ALL posts instead of just recent ones (default: last 48 hours)"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Hours to look back for new posts (default: 48)"
    )
    return parser.parse_args()


async def fetch_af_posts_recent(hours: int = 48, limit: int = 100) -> list:
    """Fetch recent Alignment Forum posts from the last N hours"""

    # Calculate the cutoff time
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff_time.isoformat()

    print(f"Fetching AF posts since {cutoff_time.strftime('%Y-%m-%d %H:%M:%S UTC')}...")

    # GraphQL query with af: true filter and after date
    query = """
    query GetRecentAFPosts($limit: Int!, $after: Date) {
      posts(input: {
        terms: {
          view: "new"
          limit: $limit
          after: $after
          af: true
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
          commentCount
          af
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

    all_posts = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Fetching recent AF posts (limit={limit})...", end=" ")

        try:
            response = await client.post(
                LESSWRONG_URL,
                json={
                    "query": query,
                    "variables": {"limit": limit, "after": cutoff_iso}
                },
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "MCP-AlignmentForum/0.1.0"
                }
            )

            if response.status_code == 200:
                data = response.json()
                if "errors" not in data:
                    posts = data.get("data", {}).get("posts", {}).get("results", [])
                    all_posts.extend(posts)
                    print(f"✅ Got {len(posts)} recent posts")
                else:
                    print(f"❌ GraphQL errors: {data['errors']}")
            else:
                print(f"❌ Status {response.status_code}: {response.text[:200]}")

        except Exception as e:
            print(f"❌ Exception: {type(e).__name__}: {e}")

    return all_posts


async def fetch_af_posts_full(limit: int = 100) -> list:
    """Fetch ALL Alignment Forum posts using pagination

    Note: The LessWrong GraphQL API has a maximum offset limit of ~2100,
    so we can fetch approximately 2100 posts maximum.
    """

    # GraphQL query with af: true filter and pagination
    query = """
    query GetAFPosts($limit: Int!, $offset: Int!) {
      posts(input: {
        terms: {
          view: "new"
          limit: $limit
          offset: $offset
          af: true
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
          commentCount
          af
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

    all_posts = []
    offset = 0
    has_more = True

    async with httpx.AsyncClient(timeout=30.0) as client:
        while has_more:
            print(f"Fetching AF posts (offset={offset}, limit={limit})...", end=" ")

            try:
                response = await client.post(
                    LESSWRONG_URL,
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
                    if "errors" not in data:
                        posts = data.get("data", {}).get("posts", {}).get("results", [])

                        if not posts:
                            print("✅ No more posts")
                            has_more = False
                        else:
                            all_posts.extend(posts)
                            print(f"✅ Got {len(posts)} posts (total: {len(all_posts)})")
                            offset += limit
                            await asyncio.sleep(GRAPHQL_DELAY)
                    else:
                        error_msg = str(data['errors'])
                        # Check if it's the "Exceeded maximum value for skip" error
                        if "Exceeded maximum value for skip" in error_msg:
                            print(f"✅ Reached API offset limit (fetched {len(all_posts)} posts)")
                        else:
                            print(f"❌ GraphQL errors: {data['errors']}")
                        has_more = False
                else:
                    print(f"❌ Status {response.status_code}: {response.text[:200]}")
                    has_more = False

            except Exception as e:
                print(f"❌ Exception: {type(e).__name__}: {e}")
                has_more = False

    return all_posts


def load_existing_posts() -> dict:
    """Load existing posts from CSV and return as dict keyed by _id"""
    existing = {}

    if not CSV_OUTPUT.exists():
        return existing

    try:
        with CSV_OUTPUT.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing[row["_id"]] = row
        print(f"Loaded {len(existing)} existing posts from CSV")
    except Exception as e:
        print(f"Warning: Could not load existing CSV: {e}")

    return existing


def post_to_csv_row(post: dict) -> dict:
    """Convert a post object to a CSV row"""
    # Handle cases where post might be None or missing fields
    if not post:
        return None

    try:
        contents = post.get("contents") or {}
        user = post.get("user") or {}

        summary = contents.get("plaintextDescription", "")
        if len(summary) > 500:
            summary = summary[:497] + "..."

        return {
            "_id": post.get("_id", ""),
            "slug": post.get("slug", ""),
            "title": post.get("title", ""),
            "summary": summary,
            "pageUrl": post.get("pageUrl", ""),
            "author": user.get("displayName", "Unknown"),
            "authorSlug": user.get("slug", ""),
            "karma": str(post.get("baseScore", 0)),
            "voteCount": str(post.get("voteCount", 0)),
            "commentsCount": str(post.get("commentCount", 0)),
            "postedAt": post.get("postedAt", ""),
            "wordCount": str(contents.get("wordCount", 0)),
            "af": str(post.get("af", False))
        }
    except (KeyError, TypeError, AttributeError) as e:
        print(f"Warning: Error processing post: {e}")
        print(f"Post data: {post}")
        return None


def write_csv(posts_dict: dict):
    """Write posts to CSV, sorted by postedAt (newest first)"""
    # Sort by postedAt descending (newest first)
    sorted_posts = sorted(
        posts_dict.values(),
        key=lambda x: x["postedAt"],
        reverse=True
    )

    CSV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["_id", "slug", "title", "summary", "pageUrl", "author",
                  "authorSlug", "karma", "voteCount", "commentsCount", "postedAt", "wordCount", "af"]

    with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(sorted_posts)


async def main():
    args = parse_args()

    print("=" * 70)
    if args.full:
        print("FETCHING ALL ALIGNMENT FORUM POSTS (FULL REFRESH)")
    else:
        print(f"FETCHING NEW ALIGNMENT FORUM POSTS (LAST {args.hours} HOURS)")
    print("=" * 70)
    print()
    print("Using LessWrong GraphQL API with af=true filter")
    print()

    # Fetch posts based on mode
    if args.full:
        new_posts = await fetch_af_posts_full(limit=100)
        existing_posts = {}  # Don't load existing in full mode
    else:
        new_posts = await fetch_af_posts_recent(hours=args.hours, limit=100)
        existing_posts = load_existing_posts()

    if not new_posts and not existing_posts:
        print("\n❌ No posts found")
        return

    print()
    print("=" * 70)
    if args.full:
        print(f"✅ Found {len(new_posts)} Alignment Forum posts!")
    else:
        print(f"✅ Found {len(new_posts)} new posts in last {args.hours} hours")
    print("=" * 70)
    print()

    # Convert new posts to CSV rows and merge with existing
    all_posts = existing_posts.copy()
    new_count = 0

    for post in new_posts:
        if not post:
            continue

        post_id = post.get("_id")
        if not post_id:
            continue

        csv_row = post_to_csv_row(post)
        if not csv_row:
            continue

        if post_id not in all_posts:
            all_posts[post_id] = csv_row
            new_count += 1
        else:
            # Update existing post with latest data
            all_posts[post_id] = csv_row

    if not args.full and new_count > 0:
        print(f"Adding {new_count} new posts to existing {len(existing_posts)} posts")
        print(f"Total posts in CSV: {len(all_posts)}")
        print()

    # Write CSV
    write_csv(all_posts)

    print(f"✅ CSV saved: {CSV_OUTPUT}")
    print(f"   Size: {CSV_OUTPUT.stat().st_size / 1024:.1f} KB")
    print(f"   Posts: {len(all_posts)}")

    if new_count > 0 or args.full:
        print()
        sample_posts = [post_to_csv_row(p) for p in new_posts[:5]]
        print("Sample of recent posts:")
        for i, p in enumerate(sample_posts, 1):
            print(f"\n{i}. {p['title']}")
            print(f"   Author: {p['author']}, Karma: {p['karma']}")
            print(f"   URL: {p['pageUrl']}")

    print()
    print("=" * 70)
    if args.full:
        print("SUCCESS! All Alignment Forum posts fetched!")
    elif new_count > 0:
        print(f"SUCCESS! {new_count} new posts added to CSV!")
    else:
        print("No new posts to add (CSV unchanged)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
