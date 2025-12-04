#!/usr/bin/env python3
"""Test with the EXACT query format that lesswrong-gpt uses successfully"""

import asyncio
import json
import httpx

GRAPHQL_URL = "https://www.alignmentforum.org/graphql"

# This is the EXACT query format used by lesswrong-gpt which successfully fetches posts
query = """
{
  posts(input: {terms: {view: "top"}}) {
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
        wordCount
        plaintextDescription
      }
      user {
        displayName
        slug
        username
      }
    }
  }
}
"""

async def test_query():
    print("Testing with the EXACT query format from working lesswrong-gpt project...")
    print(f"Endpoint: {GRAPHQL_URL}")
    print()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print("Sending query...")
            response = await client.post(
                GRAPHQL_URL,
                json={"query": query},
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "MCP-AlignmentForum/0.1.0"
                }
            )

            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                if "errors" in data:
                    print(f"GraphQL Errors: {json.dumps(data['errors'], indent=2)}")
                    return

                posts = data.get("data", {}).get("posts", {}).get("results", [])
                print(f"✅ SUCCESS! Got {len(posts)} posts")

                if posts:
                    print("\nFirst 3 posts:")
                    for i, post in enumerate(posts[:3], 1):
                        print(f"{i}. {post['title']}")
                        print(f"   Author: {post['user']['displayName']}, Karma: {post['baseScore']}")
                        print(f"   URL: {post['pageUrl']}")

                    print(f"\nThis query works! We can fetch {len(posts)} posts at a time.")
                    print("The query uses view='top' instead of limit/offset.")

            elif response.status_code == 429:
                print("❌ Still rate limited (429)")
                print("This IP is blocked. Try from YOUR computer!")
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text[:200]}")

    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_query())
