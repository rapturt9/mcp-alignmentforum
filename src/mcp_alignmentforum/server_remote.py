#!/usr/bin/env python3
"""MCP Server for Alignment Forum - Remote/SSE version

This version uses SSE (Server-Sent Events) transport for remote deployment.
Can be deployed to Railway, Render, Fly.io, etc.
"""

import csv
import json
import sys
from typing import Any

import httpx
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport
from mcp.server import Server
from mcp.server.sse import sse_server
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Mount

# Configuration
CSV_URL = "https://raw.githubusercontent.com/rapturt9/mcp-alignmentforum/main/data/alignment-forum-posts.csv"
GRAPHQL_URL = "https://www.alignmentforum.org/graphql"
USER_AGENT = "MCP-AlignmentForum/0.1.0"

# Initialize MCP server
app = Server("alignment-forum")


def parse_csv_from_text(csv_text: str) -> list[dict[str, str]]:
    """Parse CSV text into list of dictionaries"""
    import io
    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


async def get_graphql_client():
    """Create a GraphQL client for Alignment Forum API"""
    transport = HTTPXAsyncTransport(
        url=GRAPHQL_URL,
        headers={"User-Agent": USER_AGENT}
    )
    return Client(transport=transport, fetch_schema_from_transport=False)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="load_alignment_forum_posts",
            description="Load all Alignment Forum posts from the GitHub-hosted CSV file. "
                       "Returns metadata for all posts including titles, authors, karma, and summaries. "
                       "Use this first to see what posts are available.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="fetch_article_content",
            description="Fetch the full content of a specific Alignment Forum article. "
                       "Provide either the post ID (17 character alphanumeric) or the slug. "
                       "Returns the complete article with HTML content, metadata, and statistics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Post ID (_id field) or slug from the CSV"
                    }
                },
                "required": ["post_id"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""

    if name == "load_alignment_forum_posts":
        try:
            # Fetch CSV from GitHub
            async with httpx.AsyncClient() as client:
                response = await client.get(CSV_URL)
                response.raise_for_status()
                csv_text = response.text

            # Parse CSV
            posts = parse_csv_from_text(csv_text)

            # Return as JSON
            result = {
                "count": len(posts),
                "posts": posts
            }

            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to fetch CSV from GitHub: HTTP {e.response.status_code}"
            if e.response.status_code == 404:
                error_msg += "\nNote: Make sure to replace YOUR_USERNAME with your GitHub username in server.py"
            return [TextContent(type="text", text=f"Error: {error_msg}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error loading posts: {str(e)}")]

    elif name == "fetch_article_content":
        try:
            post_id = arguments.get("post_id")
            if not post_id:
                return [TextContent(type="text", text="Error: post_id parameter is required")]

            # Determine if input is ID (17 alphanumeric chars) or slug
            is_id = len(post_id) == 17 and post_id.isalnum()

            # Build GraphQL query
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
            """)

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
                return [TextContent(
                    type="text",
                    text=f"Error: Post not found with identifier '{post_id}'"
                )]

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

            return [TextContent(type="text", text=formatted_content)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error fetching article: {str(e)}")]

    else:
        return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]


# Create Starlette app for SSE transport
sse_app = Starlette(
    routes=[
        Mount("/sse", app=sse_server(app)),
    ]
)


def main() -> None:
    """Entry point for remote server"""
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")

    print(f"Starting MCP server on {host}:{port}")
    print(f"SSE endpoint: http://{host}:{port}/sse")

    uvicorn.run(sse_app, host=host, port=port)


if __name__ == "__main__":
    main()
