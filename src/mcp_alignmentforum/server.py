#!/usr/bin/env python3
"""MCP Server for Alignment Forum

Provides two tools:
1. load_alignment_forum_posts - Load all posts from GitHub-hosted CSV
2. fetch_article_content - Fetch full article content from Alignment Forum API
"""

import csv
import json
import sys
from typing import Any

import httpx
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configuration
CSV_URL = "https://raw.githubusercontent.com/rapturt9/mcp-alignmentforum/main/data/alignment-forum-posts.csv"
# Use LessWrong API instead of Alignment Forum to avoid rate limiting
# LessWrong and AF share infrastructure, so posts are accessible from both
GRAPHQL_URL = "https://www.lesswrong.com/graphql"
USER_AGENT = "MCP-AlignmentForum/0.1.0"

# Initialize MCP server
app = Server("alignment-forum")


def parse_csv_from_text(csv_text: str) -> list[dict[str, str]]:
    """Parse CSV text into a list of dictionaries."""
    lines = csv_text.strip().split('\n')
    reader = csv.DictReader(lines)
    return list(reader)


async def get_graphql_client() -> Client:
    """Create and return a GraphQL client for Alignment Forum."""
    transport = HTTPXAsyncTransport(
        url=GRAPHQL_URL,
        headers={"User-Agent": USER_AGENT}
    )
    return Client(
        transport=transport,
        fetch_schema_from_transport=False,
        execute_timeout=30
    )


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="load_alignment_forum_posts",
            description=(
                "Load all Alignment Forum posts from the daily-updated CSV file. "
                "Returns a JSON array with post metadata including title, summary, "
                "author, karma score, and links. Call this at the beginning of "
                "conversations to get an overview of available content."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="fetch_article_content",
            description=(
                "Fetch the full content of a specific Alignment Forum article. "
                "Provide either the post ID (_id field) or slug from the CSV. "
                "Returns the complete article with HTML content, metadata, and URL."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID (_id field) or slug of the article to fetch"
                    }
                },
                "required": ["post_id"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""

    if name == "load_alignment_forum_posts":
        try:
            # Fetch CSV from GitHub
            async with httpx.AsyncClient() as client:
                response = await client.get(CSV_URL, follow_redirects=True, timeout=30.0)
                response.raise_for_status()
                csv_text = response.text

            # Parse CSV
            posts = parse_csv_from_text(csv_text)

            # Format response
            result = {
                "count": len(posts),
                "posts": posts,
                "message": f"Loaded {len(posts)} posts from Alignment Forum"
            }

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )
            ]

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

            # Build GraphQL query - LessWrong only supports _id in selector
            if is_id:
                query = gql("""
                    query GetPost($id: String) {
                        post(input: {
                            selector: {
                                _id: $id
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
                variables = {"id": post_id}
            else:
                # For slugs, use documentId instead
                query = gql("""
                    query GetPost($documentId: String) {
                        post(input: {
                            selector: {
                                documentId: $documentId
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
                variables = {"documentId": post_id}

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


def main() -> None:
    """Entry point for the MCP server."""
    import asyncio

    async def run_server():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        sys.stderr.write("\nShutting down MCP server...\n")
        sys.exit(0)
    except Exception as e:
        sys.stderr.write(f"Fatal error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
