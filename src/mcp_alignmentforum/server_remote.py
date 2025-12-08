#!/usr/bin/env python3
"""MCP Server for Alignment Forum - Cloud Deployment with Neon PostgreSQL

This server provides tools to interact with Alignment Forum posts via MCP.
Uses Neon PostgreSQL with pgvector for semantic search and pagination.
"""

import json
import os
import re

import asyncpg
import httpx
import numpy as np
from dotenv import load_dotenv
from fastmcp import FastMCP
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport
from openai import AsyncOpenAI
from pgvector.asyncpg import register_vector

# Load environment variables
load_dotenv()

# Configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "")
GRAPHQL_URL = "https://www.lesswrong.com/graphql"
USER_AGENT = "MCP-AlignmentForum/0.2.0"
EMBEDDING_MODEL = "text-embedding-3-small"

# Initialize FastMCP server
mcp = FastMCP("alignment-forum")

# Global database pool and OpenAI client
db_pool: asyncpg.Pool | None = None
openai_client: AsyncOpenAI | None = None


async def ensure_db_initialized():
    """Ensure database connection pool is initialized."""
    global db_pool, openai_client

    if db_pool is None:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
        # Register pgvector type for the pool
        async with db_pool.acquire() as conn:
            await register_vector(conn)

    if openai_client is None:
        openai_client = AsyncOpenAI()


async def get_embedding(text: str) -> np.ndarray:
    """Generate embedding for search query."""
    await ensure_db_initialized()
    response = await openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return np.array(response.data[0].embedding, dtype=np.float32)


async def get_graphql_client():
    """Create a GraphQL client for Alignment Forum API."""
    transport = HTTPXAsyncTransport(url=GRAPHQL_URL, headers={"User-Agent": USER_AGENT})
    return Client(transport=transport, fetch_schema_from_transport=False)


async def fetch_from_url_directly(url: str) -> dict | None:
    """Fetch article content directly from the post URL as a fallback."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            html = response.text

        title_match = re.search(r"<title>([^<]+)</title>", html)
        og_title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        title = (
            og_title_match.group(1)
            if og_title_match
            else (title_match.group(1) if title_match else "Unknown Title")
        )

        author_match = re.search(r'"author":\s*\{[^}]*"displayName":\s*"([^"]+)"', html)
        author = author_match.group(1) if author_match else "Unknown Author"

        content_match = re.search(
            r'<div[^>]*class="[^"]*(?:postContent|PostsPage-postContent|ContentStyles-postBody)[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*(?:PostsPageActions|CommentSection)',
            html,
            re.DOTALL | re.IGNORECASE,
        )

        if not content_match:
            content_match = re.search(r"<article[^>]*>(.*?)</article>", html, re.DOTALL)

        html_body = (
            content_match.group(1)
            if content_match
            else "Content extraction failed. Please visit the URL directly."
        )

        return {
            "title": title,
            "author": author,
            "html_body": html_body,
            "url": url,
            "fetched_via": "direct_url",
        }
    except Exception:
        return None


@mcp.tool
async def search_posts(query: str, limit: int = 20, offset: int = 0) -> str:
    """Search Alignment Forum posts using natural language.

    Performs semantic search to find posts most relevant to your query.

    Args:
        query: Natural language search query (e.g., "mesa-optimization risks")
        limit: Maximum results (default 20, max 100)
        offset: Results to skip for pagination

    Returns:
        JSON with matching posts and similarity scores
    """
    await ensure_db_initialized()

    # Validate parameters
    limit = min(max(1, limit), 100)
    offset = max(0, offset)

    # Generate query embedding
    query_embedding = await get_embedding(query)

    async with db_pool.acquire() as conn:
        await register_vector(conn)

        # Semantic search using cosine similarity
        rows = await conn.fetch(
            """
            SELECT
                _id, slug, title, summary, page_url, author, author_slug,
                karma, vote_count, comments_count, posted_at, word_count, af,
                1 - (embedding <=> $1) as similarity
            FROM posts
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1
            LIMIT $2 OFFSET $3
            """,
            query_embedding,
            limit,
            offset,
        )

        # Get total count
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM posts WHERE embedding IS NOT NULL"
        )

    posts = [
        {
            "_id": row["_id"],
            "slug": row["slug"],
            "title": row["title"],
            "summary": row["summary"],
            "pageUrl": row["page_url"],
            "author": row["author"],
            "authorSlug": row["author_slug"],
            "karma": row["karma"],
            "voteCount": row["vote_count"],
            "commentsCount": row["comments_count"],
            "postedAt": row["posted_at"].isoformat() if row["posted_at"] else None,
            "wordCount": row["word_count"],
            "af": row["af"],
            "similarity": round(float(row["similarity"]), 4),
        }
        for row in rows
    ]

    return json.dumps(
        {
            "query": query,
            "total": total,
            "limit": limit,
            "offset": offset,
            "posts": posts,
        },
        indent=2,
    )


@mcp.tool
async def list_recent_posts(limit: int = 20, offset: int = 0) -> str:
    """List recent Alignment Forum posts chronologically.

    Returns posts sorted by publication date (newest first).

    Args:
        limit: Maximum results (default 20, max 100)
        offset: Results to skip for pagination

    Returns:
        JSON with posts array and pagination info
    """
    await ensure_db_initialized()

    limit = min(max(1, limit), 100)
    offset = max(0, offset)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                _id, slug, title, summary, page_url, author, author_slug,
                karma, vote_count, comments_count, posted_at, word_count, af
            FROM posts
            ORDER BY posted_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )

        total = await conn.fetchval("SELECT COUNT(*) FROM posts")

    posts = [
        {
            "_id": row["_id"],
            "slug": row["slug"],
            "title": row["title"],
            "summary": row["summary"],
            "pageUrl": row["page_url"],
            "author": row["author"],
            "authorSlug": row["author_slug"],
            "karma": row["karma"],
            "voteCount": row["vote_count"],
            "commentsCount": row["comments_count"],
            "postedAt": row["posted_at"].isoformat() if row["posted_at"] else None,
            "wordCount": row["word_count"],
            "af": row["af"],
        }
        for row in rows
    ]

    return json.dumps(
        {
            "total": total,
            "limit": limit,
            "offset": offset,
            "posts": posts,
        },
        indent=2,
    )


@mcp.tool
async def fetch_article_content(post_id: str, url: str | None = None) -> str:
    """Fetch the full content of a specific Alignment Forum article.

    Args:
        post_id: Post ID (_id field) or slug from the database
        url: Optional direct URL to the post (used as fallback if GraphQL fails)

    Returns the complete article with HTML content, metadata, and statistics.
    """
    if not post_id and not url:
        raise ValueError("Either post_id or url parameter is required")

    graphql_error = None

    # Try GraphQL first if we have a post_id
    if post_id:
        try:
            is_id = len(post_id) == 17 and post_id.isalnum()

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

            async with await get_graphql_client() as session:
                result = await session.execute(query, variable_values=variables)

            post = result.get("post", {}).get("result")

            if post:
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

    error_msg = f"Failed to fetch article with identifier '{post_id}'"
    if graphql_error:
        error_msg += f"\nGraphQL error: {graphql_error}"
    error_msg += "\nDirect URL fetch also failed."
    raise RuntimeError(error_msg)


# FastMCP Cloud will run the server automatically
