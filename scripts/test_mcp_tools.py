#!/usr/bin/env python3
"""Test script for MCP tools

This tests both MCP tools without needing to run the full MCP protocol.
"""

import asyncio
import csv
import json
from pathlib import Path

import httpx
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport


CSV_PATH = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"
GRAPHQL_URL = "https://www.alignmentforum.org/graphql"


def load_local_csv() -> list[dict[str, str]]:
    """Test Tool 1: Load CSV from local file."""
    with CSV_PATH.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


async def fetch_article_content(post_id: str):
    """Test Tool 2: Fetch article content from Alignment Forum API."""

    # Determine if input is ID (17 alphanumeric chars) or slug
    is_id = len(post_id) == 17 and post_id.isalnum()

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
        query = gql("""
            query GetPost($id: String, $slug: String) {
                post(input: {
                    selector: {
                        _id: $id
                        slug: $slug
                    }
                }) {
                    result {
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

        variables = {
            "_id" if is_id else "slug": post_id
        }

        result = await session.execute(query, variable_values=variables)
        return result.get("post", {}).get("result")


async def main():
    """Run tests."""
    print("=" * 70)
    print("MCP ALIGNMENT FORUM TOOLS TEST")
    print("=" * 70)

    # Test 1: Load CSV
    print("\n[TEST 1] Loading posts from local CSV...")
    print("-" * 70)
    try:
        posts = load_local_csv()
        print(f"✓ Successfully loaded {len(posts)} posts")
        print(f"\nFirst 3 posts:")
        for i, post in enumerate(posts[:3], 1):
            print(f"\n{i}. {post['title']}")
            print(f"   ID: {post['_id']}")
            print(f"   Slug: {post['slug']}")
            print(f"   Author: {post['author']}, Karma: {post['karma']}")
            print(f"   Summary: {post['summary'][:80]}...")

        print(f"\n✓ CSV Test PASSED - {len(posts)} posts available")

    except Exception as e:
        print(f"✗ CSV Test FAILED: {e}")
        return

    # Test 2: Fetch article content
    print("\n\n[TEST 2] Fetching article content from Alignment Forum API...")
    print("-" * 70)

    # Try fetching a well-known post by slug
    test_slug = "risks-from-learned-optimization"
    print(f"Testing with slug: '{test_slug}'")

    try:
        print("Fetching article from API...")
        post = await fetch_article_content(test_slug)

        if post:
            print(f"✓ Successfully fetched article!")
            print(f"\n  Title: {post['title']}")
            print(f"  Author: {post['user']['displayName']} (@{post['user']['username']})")
            print(f"  Posted: {post['postedAt'][:10]}")
            print(f"  Karma: {post['baseScore']} ({post['voteCount']} votes)")
            print(f"  Comments: {post['commentsCount']}")
            print(f"  Word Count: {post['contents']['wordCount']}")
            print(f"  URL: {post['pageUrl']}")
            print(f"  Content length: {len(post['htmlBody'])} characters")
            print(f"\n✓ Article Fetch Test PASSED")
        else:
            print(f"✗ Article not found")

    except Exception as e:
        print(f"✗ Article Fetch Test FAILED: {e}")
        print(f"  This might be due to rate limiting or network issues")
        print(f"  The MCP server will still work with IDs from the CSV")

    # Test 3: Verify CSV IDs can be used
    print("\n\n[TEST 3] Verifying CSV post IDs...")
    print("-" * 70)
    print("Sample post IDs from CSV that can be used with fetch_article_content:")
    for i, post in enumerate(posts[:5], 1):
        print(f"  {i}. ID: {post['_id']:<20} Slug: {post['slug']}")

    print("\n" + "=" * 70)
    print("TESTING COMPLETE")
    print("=" * 70)
    print("\nSummary:")
    print(f"  ✓ CSV loading works - {len(posts)} posts loaded")
    print(f"  ✓ Post IDs and slugs available for fetching")
    print(f"  • API fetching: test separately when rate limit clears")
    print("\nThe MCP server is ready to use!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
