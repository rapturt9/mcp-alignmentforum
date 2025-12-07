# GraphQL Query Testing Summary

## Overview
This document summarizes the results of testing the GraphQL queries used by the MCP Alignment Forum server against the LessWrong API.

**Test Date:** 2025-12-06
**API Endpoint:** https://www.lesswrong.com/graphql
**Test Post:** AGI Ruin: A List of Lethalities by Eliezer Yudkowsky
**Post ID:** `uMQ3cqWDPHhjtiesc`
**Post Slug:** `agi-ruin-a-list-of-lethalities`

---

## Test Results Summary

### ✅ Task 1: Query by Post ID - SUCCESS
- **Status:** Working correctly
- **HTTP Status:** 200 OK
- **Post Retrieved:** Yes
- **Output Files:**
  - `/Users/ram/Github/mcp-alignmentforum/test_outputs/graphql_raw_response.json` (122.2 KB)
  - `/Users/ram/Github/mcp-alignmentforum/test_outputs/graphql_parsed_output.json` (183.8 KB)

### ❌ Task 3: Query by Slug - FAILED
- **Status:** API validation error
- **HTTP Status:** 400 Bad Request
- **Error:** "Field 'slug' is not defined by type 'SelectorInput'"
- **Root Cause:** The LessWrong GraphQL API does not support `slug` as a selector field
- **Output File:** `/Users/ram/Github/mcp-alignmentforum/test_outputs/graphql_slug_test.json` (4.0 KB)

### ✅ Task 2: Data Flow Documentation - COMPLETE
- **Status:** Successfully documented
- **Output File:** `/Users/ram/Github/mcp-alignmentforum/test_outputs/data_flow_explanation.json` (132.6 KB)

---

## Key Findings

### 1. GraphQL Query Structure (Working)

The query that WORKS uses only `_id`:

```graphql
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
```

**Variables:** `{"id": "uMQ3cqWDPHhjtiesc"}`

### 2. Raw GraphQL Response Structure

```json
{
  "data": {
    "post": {
      "result": {
        "_id": "uMQ3cqWDPHhjtiesc",
        "slug": "agi-ruin-a-list-of-lethalities",
        "title": "AGI Ruin: A List of Lethalities",
        "pageUrl": "https://www.alignmentforum.org/posts/...",
        "postedAt": "2022-06-06T15:00:00.000Z",
        "baseScore": 318,
        "voteCount": 165,
        "commentCount": 422,
        "htmlBody": "<div>...</div>",
        "contents": {
          "html": "<div>...</div>",
          "wordCount": 9842,
          "plaintextDescription": "..."
        },
        "user": {
          "username": "EliezerYudkowsky",
          "displayName": "Eliezer Yudkowsky",
          "slug": "eliezeryudkowsky"
        }
      }
    }
  }
}
```

### 3. Data Transformation Pipeline

The MCP server transforms the raw GraphQL response through these steps:

1. **GraphQL Query Execution** → Receive nested JSON response from API
2. **Extract Post Object** → `post = result.get('post', {}).get('result')`
3. **Format as Markdown** → Transform structured data into markdown template
4. **Wrap in MCP TextContent** → Package as MCP response

**Field Mappings:**
- `post['title']` → `# {title}` (Markdown header)
- `post['user']['displayName']` + `post['user']['username']` → `**Author**: DisplayName (@username)`
- `post['postedAt'][:10]` → `**Posted**: YYYY-MM-DD`
- `post['baseScore']` + `post['voteCount']` → `**Karma**: score (votes)`
- `post['commentCount']` → `**Comments**: count`
- `post['contents']['wordCount']` → `**Word Count**: count`
- `post['pageUrl']` → `**URL**: url`
- `post['htmlBody']` → Main article content

**Unused Fields (returned but not displayed):**
- `contents.html` - Duplicate of htmlBody
- `contents.plaintextDescription` - Summary not shown
- `user.slug` - Author slug not displayed
- `_id` - Internal ID not shown to user
- `slug` - URL slug not displayed (pageUrl used instead)

### 4. Example Formatted Output

```markdown
# AGI Ruin: A List of Lethalities

**Author**: Eliezer Yudkowsky (@EliezerYudkowsky)
**Posted**: 2022-06-06
**Karma**: 318 (165 votes)
**Comments**: 422
**Word Count**: 9842
**URL**: https://www.alignmentforum.org/posts/uMQ3cqWDPHhjtiesc/agi-ruin-a-list-of-lethalities

---

<div>...HTML content...</div>

---

*Fetched from Alignment Forum via MCP*
```

---

## Critical Issue Found: server.py GraphQL Query Bug

### Problem
The current implementation in `/Users/ram/Github/mcp-alignmentforum/src/mcp_alignmentforum/server.py` (lines 138-169) attempts to use both `_id` and `slug` in the same GraphQL selector:

```python
query = gql("""
    query GetPost($id: String, $slug: String) {
        post(input: {
            selector: {
                _id: $id
                slug: $slug    # ❌ NOT SUPPORTED BY API
            }
        }) {
            ...
        }
    }
""")
```

### API Error Response
```json
{
  "errors": [
    {
      "message": "Field 'slug' is not defined by type 'SelectorInput'.",
      "extensions": {
        "code": "GRAPHQL_VALIDATION_FAILED"
      }
    }
  ]
}
```

### Impact
- The slug-based lookup functionality does **NOT** work
- Any attempt to fetch an article using a slug will fail with a 400 error
- The server code has never been properly tested with the actual API

### Recommended Fix
The server should use conditional queries - separate queries for ID vs slug lookups:

```python
# Determine if input is ID or slug
is_id = len(post_id) == 17 and post_id.isalnum()

# Use different queries based on input type
if is_id:
    query = gql("""
        query GetPost($id: String!) {
            post(input: { selector: { _id: $id } }) {
                result { ... }
            }
        }
    """)
    variables = {"id": post_id}
else:
    # Need to find alternative approach - slug selector doesn't work
    # Options:
    # 1. Only support ID-based lookups
    # 2. Fetch by constructing URL pattern
    # 3. Use a different API endpoint
```

---

## Output Files Generated

All output files are saved in: `/Users/ram/Github/mcp-alignmentforum/test_outputs/`

| File | Size | Description |
|------|------|-------------|
| `graphql_raw_response.json` | 122.2 KB | Complete raw GraphQL API response for ID-based query |
| `graphql_parsed_output.json` | 183.8 KB | Parsed/transformed output showing full transformation pipeline |
| `data_flow_explanation.json` | 132.6 KB | Comprehensive data flow documentation with field mappings |
| `graphql_slug_test.json` | 4.0 KB | Slug-based query test results (failed with API error) |

---

## Recommendations

1. **Fix the GraphQL query in server.py** - Remove the slug parameter from the selector or implement proper conditional queries
2. **Consider ID-only approach** - Since slug lookups don't work via GraphQL selector, consider only supporting ID-based lookups
3. **Add API schema validation** - Test queries against the actual API schema during development
4. **Update documentation** - Clarify that only post IDs (not slugs) are supported for article fetching
5. **Add integration tests** - Create tests that validate against the real API to catch these issues earlier

---

## Test Script

The test script used to generate these results is available at:
`/Users/ram/Github/mcp-alignmentforum/test_graphql_queries.py`

To reproduce these tests:
```bash
python test_graphql_queries.py
```

---

## Additional Notes

- The API returns HTML content in the `htmlBody` field (~61KB for this test post)
- The `contents.html` field contains duplicate HTML content
- The API response includes both alignment forum and LessWrong posts (they share infrastructure)
- Authentication is not required for public posts
- Rate limiting may apply for high-volume requests
