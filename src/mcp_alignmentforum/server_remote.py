#!/usr/bin/env python3
"""MCP Server for Alignment Forum - Cloud Deployment

This server provides tools to interact with Alignment Forum posts via MCP.
Designed for deployment to FastMCP Cloud or similar platforms.
"""

import csv
import json
import re

import httpx
from fastmcp import FastMCP
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport

# Configuration
CSV_URL = "https://raw.githubusercontent.com/rapturt9/mcp-alignmentforum/main/data/alignment-forum-posts.csv"
# Use LessWrong API instead of Alignment Forum to avoid rate limiting
# LessWrong and AF share infrastructure, so posts are accessible from both
GRAPHQL_URL = "https://www.lesswrong.com/graphql"
USER_AGENT = "MCP-AlignmentForum/0.1.0"

# Initialize FastMCP server
mcp = FastMCP("alignment-forum")


def parse_csv_from_text(csv_text: str) -> list[dict[str, str]]:
    """Parse CSV text into list of dictionaries"""
    import io

    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


async def get_graphql_client():
    """Create a GraphQL client for Alignment Forum API"""
    transport = HTTPXAsyncTransport(url=GRAPHQL_URL, headers={"User-Agent": USER_AGENT})
    return Client(transport=transport, fetch_schema_from_transport=False)


async def fetch_from_url_directly(url: str) -> dict | None:
    """Fetch article content directly from the post URL as a fallback.

    Parses the HTML page to extract article content when GraphQL fails.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            html = response.text

        # Extract title from <title> or og:title
        title_match = re.search(r'<title>([^<]+)</title>', html)
        og_title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        title = og_title_match.group(1) if og_title_match else (title_match.group(1) if title_match else "Unknown Title")

        # Extract author from meta or structured data
        author_match = re.search(r'"author":\s*\{[^}]*"displayName":\s*"([^"]+)"', html)
        author = author_match.group(1) if author_match else "Unknown Author"

        # Extract the main content - look for the post body div
        # LessWrong/AF uses class patterns like "PostsPage-postContent" or similar
        content_match = re.search(
            r'<div[^>]*class="[^"]*(?:postContent|PostsPage-postContent|ContentStyles-postBody)[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*(?:PostsPageActions|CommentSection)',
            html,
            re.DOTALL | re.IGNORECASE
        )

        if not content_match:
            # Try a more general approach - find content between markers
            content_match = re.search(
                r'<article[^>]*>(.*?)</article>',
                html,
                re.DOTALL
            )

        html_body = content_match.group(1) if content_match else "Content extraction failed. Please visit the URL directly."

        return {
            "title": title,
            "author": author,
            "html_body": html_body,
            "url": url,
            "fetched_via": "direct_url"
        }
    except Exception:
        return None


@mcp.tool
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


@mcp.tool
async def fetch_article_content(post_id: str, url: str | None = None) -> str:
    """Fetch the full content of a specific Alignment Forum article.

    Args:
        post_id: Post ID (_id field) or slug from the CSV
        url: Optional direct URL to the post (used as fallback if GraphQL fails)

    Returns the complete article with HTML content, metadata, and statistics.
    """
    if not post_id and not url:
        raise ValueError("Either post_id or url parameter is required")

    graphql_error = None

    # Try GraphQL first if we have a post_id
    if post_id:
        try:
            # Determine if input is ID (17 alphanumeric chars) or slug
            is_id = len(post_id) == 17 and post_id.isalnum()

            # Build GraphQL query - LessWrong only supports _id in selector
            if is_id:
                query = gql(
                    """
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
                """
                )
                variables = {"id": post_id}
            else:
                # For slugs, use documentId instead
                query = gql(
                    """
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
                """
                )
                variables = {"documentId": post_id}

            # Execute query
            async with await get_graphql_client() as session:
                result = await session.execute(query, variable_values=variables)

            post = result.get("post", {}).get("result")

            if post:
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

*Fetched from Alignment Forum via MCP (GraphQL)*
"""
                return formatted_content

        except Exception as e:
            graphql_error = str(e)

    # Fallback: Try fetching directly from URL
    fallback_url = url
    if not fallback_url and post_id:
        # Construct URL from post_id (works for both ID and slug)
        fallback_url = f"https://www.alignmentforum.org/posts/{post_id}"

    if fallback_url:
        result = await fetch_from_url_directly(fallback_url)
        if result:
            formatted_content = f"""# {result['title']}

**Author**: {result['author']}
**URL**: {result['url']}

---

{result['html_body']}

---

*Fetched from Alignment Forum via MCP (direct URL fallback)*
"""
            return formatted_content

    # Both methods failed
    error_msg = f"Failed to fetch article with identifier '{post_id}'"
    if graphql_error:
        error_msg += f"\nGraphQL error: {graphql_error}"
    error_msg += "\nDirect URL fetch also failed."
    raise RuntimeError(error_msg)


# FastMCP Cloud will run the server automatically
# No need for if __name__ == "__main__" block
