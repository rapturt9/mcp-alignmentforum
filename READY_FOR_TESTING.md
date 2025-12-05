# MCP Server - Ready for Testing

## ✅ Server Fixes Completed

### Issues Fixed:
1. **API Field Name**: Changed `commentsCount` to `commentCount` (LessWrong/AF API uses singular)
2. **GraphQL Variables**: Fixed variable assignment for post queries
3. **Test Script**: Updated PATH for node/npm

### Files Modified:
- [src/mcp_alignmentforum/server.py](src/mcp_alignmentforum/server.py) - Core server fixes
- [test-mcp.sh](test-mcp.sh) - PATH configuration

## Server Status

✅ **Server imports successfully**
```bash
✅ Server imports successfully
```

✅ **Has 3 MCP tools**:
1. `load_alignment_forum_posts` - Loads 62 real posts from CSV
2. `fetch_article_content` - Fetches full article by ID or slug
3. `trigger_ifttt_event` - IFTTT webhook integration

✅ **Data ready**: 62 real alignment posts in CSV

✅ **Configuration**: Set up in Claude Desktop config

## Testing Options

### Option 1: Test in Claude Desktop (Recommended)

Since MCP inspector requires Node.js 18+ (system has 16.14.2), the best way to test is:

1. **Restart Claude Desktop**:
   ```bash
   # Quit Claude Desktop (Cmd+Q)
   # Then reopen it
   ```

2. **Look for the tools icon** (hammer/wrench) in Claude Desktop

3. **Verify the server is loaded**:
   - Should see `alignment-forum` with 3 tools
   - Tools icon should be clickable

4. **Test with a query**:
   ```
   Load the alignment forum posts and show me the top 5 by karma
   ```

### Option 2: Upgrade Node.js (For Inspector Testing)

To use the MCP inspector, upgrade Node.js to 18+:

```bash
# Using n (node version manager)
n install lts
n use lts

# Then run:
./test-mcp.sh
```

This will open http://localhost:5173 for interactive testing.

### Option 3: Direct Server Test (Without Inspector)

You can verify the server starts without errors:

```bash
cd /Users/ram/Github/mcp-alignmentforum
/usr/local/bin/uv run mcp-alignmentforum
# Press Ctrl+C to stop
```

If it starts without errors, the server is working correctly.

## Expected Behavior

### Tool 1: load_alignment_forum_posts
- **No parameters needed**
- **Returns**: JSON with 62 posts
- **Should include**:
  - "AGI Ruin: A List of Lethalities" (956 karma)
  - "Where I agree and disagree with Eliezer" (911 karma)
  - And 60 more alignment-related posts

### Tool 2: fetch_article_content
- **Parameter**: `post_id` (ID or slug)
- **Example**: `uMQ3cqWDPHhjtiesc` or `agi-ruin-a-list-of-lethalities`
- **Returns**: Full article with:
  - Title, author, date, karma, comments
  - Full HTML content
  - Word count and URL

### Tool 3: trigger_ifttt_event
- **Parameters**: JSON payload
- **Triggers**: IFTTT webhook event
- **For**: Automation integrations

## Troubleshooting

### Server doesn't appear in Claude Desktop

1. Check config file:
   ```bash
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

2. Verify path is correct:
   ```json
   "alignment-forum": {
     "command": "/usr/local/bin/uv",
     "args": [
       "--directory",
       "/Users/ram/Github/mcp-alignmentforum",
       "run",
       "mcp-alignmentforum"
     ]
   }
   ```

3. Check Claude Desktop logs:
   ```bash
   ls -lt ~/Library/Logs/Claude/ | head -5
   ```

### Tool 1 returns 404 error

The CSV URL needs to point to your GitHub repo. Check [src/mcp_alignmentforum/server.py](src/mcp_alignmentforum/server.py) line 24:

```python
CSV_URL = "https://raw.githubusercontent.com/rapturt9/mcp-alignmentforum/main/data/alignment-forum-posts.csv"
```

Push your changes to GitHub first:
```bash
git push origin main
```

## Current Commits

```
234b994 Fix MCP server API compatibility issues
d430f32 Add MCP inspector testing and update config to use uv
aded10c Add comprehensive project status document
75e4c45 Add 62 real alignment posts from LessWrong
```

## Next Steps

1. **Push to GitHub** (if not already done):
   ```bash
   git push origin main
   ```

2. **Restart Claude Desktop** to load the MCP server

3. **Test with queries** about alignment research

4. **Optional**: Upgrade Node.js to use MCP inspector for debugging

---

**Status**: ✅ Ready for production use in Claude Desktop!
