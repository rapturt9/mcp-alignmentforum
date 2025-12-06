#!/usr/bin/env python3
"""MCP Server for Alignment Forum - Remote/HTTP version

This version uses Streamable HTTP transport for remote deployment.
Can be deployed to Railway, Render, Fly.io, etc.
"""

import csv
import json
import os
from typing import Any

import httpx
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport
from mcp.server.fastmcp import FastMCP

# Configuration
CSV_URL = "https://raw.githubusercontent.com/rapturt9/mcp-alignmentforum/main/data/alignment-forum-posts.csv"
GRAPHQL_URL = "https://www.alignmentforum.org/graphql"
USER_AGENT = "MCP-AlignmentForum/0.1.0"

# Initialize FastMCP server with stateless HTTP and JSON responses
mcp = FastMCP(
    "alignment-forum",
    stateless_http=True,
    json_response=True
)


def parse_csv_from_text(csv_text: str) -> list[dict[str, str]]:
    """Parse CSV text into list of dictionaries"""
    import io

    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


async def get_graphql_client():
    """Create a GraphQL client for Alignment Forum API"""
    transport = HTTPXAsyncTransport(url=GRAPHQL_URL, headers={"User-Agent": USER_AGENT})
    return Client(transport=transport, fetch_schema_from_transport=False)


@mcp.tool()
async def load_alignment_forum_posts() -> str:
    """Load all Alignment Forum posts from the GitHub-hosted CSV file.

    Returns metadata for all posts including titles, authors, karma, and summaries.
    Use this first to see what posts are available.
    """
    try:
        # Fetch CSV from GitHub
        async with httpx.AsyncClient() as client:
            response = await client.get(CSV_URL)
            response.raise_for_status()
            csv_text = response.text

        # Parse CSV
        posts = parse_csv_from_text(csv_text)

        # Return as JSON
        result = {"count": len(posts), "posts": posts}

        return json.dumps(result, indent=2)

    except httpx.HTTPStatusError as e:
        error_msg = f"Failed to fetch CSV from GitHub: HTTP {e.response.status_code}"
        if e.response.status_code == 404:
            error_msg += "\nNote: Make sure the CSV exists on GitHub"
        raise RuntimeError(error_msg)
    except Exception as e:
        raise RuntimeError(f"Error loading posts: {str(e)}")


@mcp.tool()
async def fetch_article_content(post_id: str) -> str:
    """Fetch the full content of a specific Alignment Forum article.

    Args:
        post_id: Post ID (_id field) or slug from the CSV

    Returns the complete article with HTML content, metadata, and statistics.
    """
    try:
        if not post_id:
            raise ValueError("post_id parameter is required")

        # Determine if input is ID (17 alphanumeric chars) or slug
        is_id = len(post_id) == 17 and post_id.isalnum()

        # Build GraphQL query
        query = gql(
            """
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
                        commentCount
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
        """
        )

        # Set variables based on input type
        if is_id:
            variables = {"id": post_id, "slug": None}
        else:
            variables = {"id": None, "slug": post_id}

        # Execute query
        async with await get_graphql_client() as session:
            result = await session.execute(query, variable_values=variables)

        post = result.get("post", {}).get("result")

        if not post:
            raise ValueError(f"Post not found with identifier '{post_id}'")

        # Format the article content
        formatted_content = f"""# {post['title']}

**Author**: {post['user']['displayName']} (@{post['user']['username']})
**Posted**: {post['postedAt'][:10]}
**Karma**: {post['baseScore']} ({post['voteCount']} votes)
**Comments**: {post['commentCount']}
**Word Count**: {post['contents']['wordCount']}
**URL**: {post['pageUrl']}

---

{post['htmlBody']}

---

*Fetched from Alignment Forum via MCP*
"""

        return formatted_content

    except Exception as e:
        raise RuntimeError(f"Error fetching article: {str(e)}")


def main() -> None:
    """Entry point for remote server"""
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")

    # Get Railway public URLs
    public_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    static_url = os.environ.get("RAILWAY_STATIC_URL", "")

    print("=" * 70)
    print("MCP ALIGNMENT FORUM SERVER (Streamable HTTP)")
    print("=" * 70)
    print(f"Starting server on {host}:{port}")
    print()

    if public_domain:
        print(f"Public URL: https://{public_domain}")
        print(f"MCP Endpoint: https://{public_domain}/mcp")
        print(f"Health Check: https://{public_domain}/health")
    elif static_url:
        print(f"Public URL: https://{static_url}")
        print(f"MCP Endpoint: https://{static_url}/mcp")
        print(f"Health Check: https://{static_url}/health")
    else:
        print(f"Local URL: http://{host}:{port}")
        print(f"MCP Endpoint: http://{host}:{port}/mcp")
        print(f"Health Check: http://{host}:{port}/health")

    print()
    print("Available Tools:")
    print("  - load_alignment_forum_posts")
    print("  - fetch_article_content")
    print("=" * 70)

    # Run FastMCP with streamable HTTP transport
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port
    )


if __name__ == "__main__":
    main()
