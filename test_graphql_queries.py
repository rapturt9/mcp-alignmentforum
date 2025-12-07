#!/usr/bin/env python3
"""Test GraphQL queries for MCP Alignment Forum server

This script tests the GraphQL queries used by the MCP server and creates
detailed JSON output files showing the data flow and transformations.
"""

import asyncio
import json
from pathlib import Path

import httpx

# Configuration
GRAPHQL_URL = "https://www.lesswrong.com/graphql"
USER_AGENT = "MCP-AlignmentForum/0.1.0"
OUTPUT_DIR = Path("/Users/ram/Github/mcp-alignmentforum/test_outputs")

# Test data
TEST_POST_ID = "uMQ3cqWDPHhjtiesc"  # AGI Ruin post
TEST_POST_SLUG = "agi-ruin-a-list-of-lethalities"


def format_article_content(post: dict) -> str:
    """Format article content exactly as server.py does."""
    return f"""# {post['title']}

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


def create_transformation_analysis(raw_response: dict) -> dict:
    """Analyze how raw GraphQL response transforms to final output."""
    post = raw_response.get("data", {}).get("post", {}).get("result", {})

    return {
        "description": "Data flow from GraphQL response to MCP output",
        "transformations": [
            {
                "step": 1,
                "name": "GraphQL Query Execution",
                "description": "Execute GraphQL query against LessWrong API",
                "output": "Nested JSON response with post data"
            },
            {
                "step": 2,
                "name": "Extract Post Object",
                "description": "Extract post.result from GraphQL response",
                "code": "post = result.get('post', {}).get('result')",
                "output": post
            },
            {
                "step": 3,
                "name": "Format as Markdown",
                "description": "Transform structured data into markdown template",
                "field_mappings": {
                    "title": {
                        "source": "post['title']",
                        "usage": "Markdown header (# title)",
                        "value": post.get('title')
                    },
                    "author": {
                        "source": "post['user']['displayName'] and post['user']['username']",
                        "usage": "**Author**: DisplayName (@username)",
                        "value": f"{post.get('user', {}).get('displayName')} (@{post.get('user', {}).get('username')})"
                    },
                    "posted_date": {
                        "source": "post['postedAt'][:10]",
                        "usage": "**Posted**: YYYY-MM-DD",
                        "value": post.get('postedAt', '')[:10] if post.get('postedAt') else None
                    },
                    "karma": {
                        "source": "post['baseScore'] and post['voteCount']",
                        "usage": "**Karma**: score (count votes)",
                        "value": f"{post.get('baseScore')} ({post.get('voteCount')} votes)"
                    },
                    "comments": {
                        "source": "post['commentCount']",
                        "usage": "**Comments**: count",
                        "value": post.get('commentCount')
                    },
                    "word_count": {
                        "source": "post['contents']['wordCount']",
                        "usage": "**Word Count**: count",
                        "value": post.get('contents', {}).get('wordCount')
                    },
                    "url": {
                        "source": "post['pageUrl']",
                        "usage": "**URL**: url",
                        "value": post.get('pageUrl')
                    },
                    "content": {
                        "source": "post['htmlBody']",
                        "usage": "Main article content (HTML)",
                        "value_preview": post.get('htmlBody', '')[:200] + "..." if post.get('htmlBody') else None
                    }
                }
            },
            {
                "step": 4,
                "name": "Wrap in MCP TextContent",
                "description": "Package markdown as MCP TextContent response",
                "code": "TextContent(type='text', text=formatted_content)",
                "output_format": {
                    "type": "TextContent",
                    "fields": {
                        "type": "text",
                        "text": "Formatted markdown string"
                    }
                }
            }
        ],
        "unused_fields": {
            "description": "Fields returned by GraphQL but not used in final output",
            "fields": [
                {
                    "name": "contents.html",
                    "reason": "Duplicate of htmlBody, htmlBody is preferred",
                    "value_preview": post.get('contents', {}).get('html', '')[:100] + "..." if post.get('contents', {}).get('html') else None
                },
                {
                    "name": "contents.plaintextDescription",
                    "reason": "Summary/preview not included in detail view",
                    "value": post.get('contents', {}).get('plaintextDescription')
                },
                {
                    "name": "user.slug",
                    "reason": "Not displayed in output, only username and displayName used",
                    "value": post.get('user', {}).get('slug')
                },
                {
                    "name": "_id",
                    "reason": "Internal identifier not shown to user",
                    "value": post.get('_id')
                },
                {
                    "name": "slug",
                    "reason": "URL-friendly identifier, pageUrl used instead",
                    "value": post.get('slug')
                }
            ]
        }
    }


async def execute_graphql_query(query: str, variables: dict) -> dict:
    """Execute a GraphQL query using httpx."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"User-Agent": USER_AGENT},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


async def test_query_by_id():
    """Test fetching article by ID."""
    print(f"\n=== Testing query with ID: {TEST_POST_ID} ===")

    # Query with just _id
    query = """
        query GetPost($id: String!) {
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

    variables = {"id": TEST_POST_ID}
    result = await execute_graphql_query(query, variables)

    # Save raw response
    raw_output_path = OUTPUT_DIR / "graphql_raw_response.json"
    with open(raw_output_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"✓ Saved raw response to: {raw_output_path}")

    # Create parsed/formatted version
    post = result.get("data", {}).get("post", {}).get("result")
    if post:
        formatted_content = format_article_content(post)

        parsed_output = {
            "description": "Parsed and formatted output for MCP response",
            "query_type": "by_id",
            "query_input": {
                "post_id": TEST_POST_ID,
                "is_id_format": True
            },
            "graphql_query": query.strip(),
            "graphql_variables": variables,
            "extracted_post": post,
            "formatted_markdown": formatted_content,
            "output_type": "TextContent",
            "markdown_preview": formatted_content[:500] + "..." if len(formatted_content) > 500 else formatted_content
        }

        parsed_output_path = OUTPUT_DIR / "graphql_parsed_output.json"
        with open(parsed_output_path, 'w') as f:
            json.dump(parsed_output, f, indent=2)
        print(f"✓ Saved parsed output to: {parsed_output_path}")
    else:
        print(f"✗ No post found in response")
        if "errors" in result:
            print(f"  Errors: {result['errors']}")

    return result


async def test_query_by_slug():
    """Test fetching article by slug."""
    print(f"\n=== Testing query with slug: {TEST_POST_SLUG} ===")

    # Test if slug works as a separate query
    query = """
        query GetPost($slug: String!) {
            post(input: {
                selector: {
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

    variables = {"slug": TEST_POST_SLUG}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers={"User-Agent": USER_AGENT},
                timeout=30.0
            )
            result = response.json()  # Get JSON even if status is error

        post = result.get("data", {}).get("post", {}).get("result") if "data" in result else None

        slug_test_output = {
            "description": "Test query using slug instead of ID",
            "query_type": "by_slug",
            "query_input": {
                "slug": TEST_POST_SLUG,
                "is_id_format": False
            },
            "graphql_query": query.strip(),
            "graphql_variables": variables,
            "http_status": response.status_code,
            "success": post is not None,
            "errors": result.get("errors"),
            "post_retrieved": {
                "_id": post.get("_id") if post else None,
                "slug": post.get("slug") if post else None,
                "title": post.get("title") if post else None
            } if post else None,
            "verification": {
                "expected_id": TEST_POST_ID,
                "actual_id": post.get("_id") if post else None,
                "id_matches": post.get("_id") == TEST_POST_ID if post else False,
                "message": "Both ID and slug lookups return the same post" if post and post.get("_id") == TEST_POST_ID else "Mismatch or error"
            },
            "full_response": result
        }

        slug_output_path = OUTPUT_DIR / "graphql_slug_test.json"
        with open(slug_output_path, 'w') as f:
            json.dump(slug_test_output, f, indent=2)

        if post:
            print(f"✓ Saved slug test to: {slug_output_path}")
        else:
            print(f"✗ Slug query failed (HTTP {response.status_code})")
            print(f"✓ Saved error details to: {slug_output_path}")

        return result
    except Exception as e:
        print(f"✗ Error testing slug query: {e}")
        error_output = {
            "description": "Test query using slug instead of ID",
            "query_type": "by_slug",
            "success": False,
            "error": str(e),
            "note": "Slug parameter may not be supported in selector"
        }
        slug_output_path = OUTPUT_DIR / "graphql_slug_test.json"
        with open(slug_output_path, 'w') as f:
            json.dump(error_output, f, indent=2)
        print(f"✓ Saved error result to: {slug_output_path}")


async def create_data_flow_explanation(raw_response: dict):
    """Create comprehensive data flow explanation."""
    print("\n=== Creating data flow explanation ===")

    transformation_analysis = create_transformation_analysis(raw_response)
    post = raw_response.get("data", {}).get("post", {}).get("result", {})

    data_flow = {
        "overview": {
            "description": "Complete data flow from GraphQL API to MCP client",
            "source": "LessWrong GraphQL API (https://www.lesswrong.com/graphql)",
            "endpoint": GRAPHQL_URL,
            "query_name": "GetPost",
            "parameters": ["id (String, required) OR slug (String, required)"],
            "response_format": "JSON with nested structure",
            "note": "The API requires EITHER _id OR slug in separate queries, not both in the same selector"
        },
        "query_structure": {
            "description": "GraphQL query structure and field selection",
            "query_by_id": {
                "selector": {"_id": "$id"},
                "variables": {"id": "String!"}
            },
            "query_by_slug": {
                "selector": {"slug": "$slug"},
                "variables": {"slug": "String!"}
            },
            "returned_fields": {
                "post.result._id": "Unique post identifier",
                "post.result.slug": "URL-friendly post identifier",
                "post.result.title": "Post title",
                "post.result.pageUrl": "Full URL to post",
                "post.result.postedAt": "ISO 8601 timestamp",
                "post.result.baseScore": "Karma score",
                "post.result.voteCount": "Number of votes",
                "post.result.commentCount": "Number of comments",
                "post.result.htmlBody": "HTML content of post",
                "post.result.contents.html": "Alternative HTML content",
                "post.result.contents.wordCount": "Word count",
                "post.result.contents.plaintextDescription": "Plain text summary",
                "post.result.user.username": "Author username",
                "post.result.user.displayName": "Author display name",
                "post.result.user.slug": "Author profile slug"
            },
            "input_handling": {
                "description": "How post_id parameter determines query variables",
                "logic": "If len(post_id) == 17 and post_id.isalnum() then use as ID, else use as slug",
                "example_id": {
                    "input": TEST_POST_ID,
                    "is_id": True,
                    "query_uses": "_id selector",
                    "variables": {"id": TEST_POST_ID}
                },
                "example_slug": {
                    "input": TEST_POST_SLUG,
                    "is_id": False,
                    "query_uses": "slug selector",
                    "variables": {"slug": TEST_POST_SLUG}
                }
            }
        },
        "transformation_steps": transformation_analysis,
        "example_data": {
            "description": "Example showing actual data at each step",
            "raw_graphql_response_excerpt": {
                "data": {
                    "post": {
                        "result": {
                            "_id": post.get("_id"),
                            "title": post.get("title"),
                            "user": post.get("user"),
                            "baseScore": post.get("baseScore"),
                            "voteCount": post.get("voteCount"),
                            "commentCount": post.get("commentCount"),
                            "pageUrl": post.get("pageUrl")
                        }
                    }
                }
            },
            "formatted_markdown_excerpt": format_article_content(post).split("---")[0] if post else None
        },
        "error_handling": {
            "null_post": {
                "condition": "post.result is None or missing",
                "response": "Error: Post not found with identifier '{post_id}'"
            },
            "network_errors": {
                "condition": "HTTP errors, timeouts, connection issues",
                "response": "Error fetching article: {error_message}"
            },
            "missing_parameter": {
                "condition": "post_id not provided",
                "response": "Error: post_id parameter is required"
            }
        },
        "mcp_integration": {
            "tool_name": "fetch_article_content",
            "input_schema": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The post ID (_id field) or slug of the article to fetch"
                    }
                },
                "required": ["post_id"]
            },
            "output_format": "MCP TextContent with markdown string",
            "output_example": {
                "type": "text",
                "text": "# Article Title\\n\\n**Author**: Name (@username)\\n..."
            }
        },
        "api_quirks": {
            "selector_limitation": {
                "description": "The API does not support both _id and slug in the same selector object",
                "workaround": "Server.py should use conditional queries - one query for _id, another for slug",
                "current_implementation_issue": "The server.py code attempts to pass both _id and slug in same selector, which may cause validation errors"
            }
        }
    }

    flow_output_path = OUTPUT_DIR / "data_flow_explanation.json"
    with open(flow_output_path, 'w') as f:
        json.dump(data_flow, f, indent=2)
    print(f"✓ Saved data flow explanation to: {flow_output_path}")


async def main():
    """Run all tests and generate output files."""
    print("Starting GraphQL query tests for MCP Alignment Forum server")
    print(f"Output directory: {OUTPUT_DIR}")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Created output directory")

    try:
        # Task 1: Test query by ID
        raw_response = await test_query_by_id()

        # Task 2: Create data flow explanation
        await create_data_flow_explanation(raw_response)

        # Task 3: Test query by slug
        await test_query_by_slug()

        print("\n" + "="*60)
        print("All tests completed successfully!")
        print("="*60)
        print("\nGenerated files:")
        for file in sorted(OUTPUT_DIR.glob("*.json")):
            size_kb = file.stat().st_size / 1024
            print(f"  - {file.name} ({size_kb:.1f} KB)")

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
