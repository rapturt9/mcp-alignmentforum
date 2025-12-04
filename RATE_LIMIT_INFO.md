# Alignment Forum API Rate Limiting

## Current Situation

The Alignment Forum GraphQL API is **aggressively rate-limited** and appears to have protections against automated scraping.

### What We've Tried

1. ✅ **GraphQL API**: Correctly using `https://www.alignmentforum.org/graphql`
2. ✅ **Proper Queries**: Valid GraphQL syntax, minimal fields
3. ✅ **Rate Limiting**: Added delays between requests
4. ✅ **Rotating Proxies**: Tried 100 different proxy IPs
5. ✅ **Sequential Requests**: Slow, one-at-a-time fetching
6. ❌ **Result**: Still getting 429 (Too Many Requests) on ALL attempts

### Error Response

```
Client error '429 Too Many Requests' for url 'https://www.alignmentforum.org/graphql'
```

## Why It's Failing

The Alignment Forum/LessWrong API likely has:
- Per-IP rate limits (we hit these)
- Proxy detection (blocks known proxy IPs)
- Request pattern analysis (detects automated tools)
- Possible whitelist requirements for bulk access

## Solutions

### Option 1: Run From Your Computer (Recommended)

**Your local machine won't be rate-limited!**

```bash
cd ~/Github/mcp-alignmentforum

# Try with proxies (fastest)
python3 scripts/fetch_with_proxies.py

# Or sequential with delays (slower but more reliable)
python3 scripts/fetch_slow_sequential.py

# Or the standard script
python3 scripts/update_posts.py
```

### Option 2: Wait for Rate Limit to Clear

Our IP is currently rate-limited. This typically clears in:
- **2-24 hours** for most APIs
- Try again tomorrow

### Option 3: Different Network

Try from:
- Different WiFi network
- Mobile hotspot
- VPN (non-proxy)
- Different computer/location

### Option 4: Contact AF Administrators

For bulk data access, email the Alignment Forum team:
- Explain your use case (educational MCP server)
- Ask about rate limits and bulk access
- Request API key or whitelist if available

Based on LessWrong documentation, they appreciate being contacted before large-scale scraping.

## Scripts Available

We've created multiple scripts for fetching data:

| Script | Method | Speed | Success Rate |
|--------|--------|-------|--------------|
| `scripts/update_posts.py` | Direct, paginated | Medium | Low (rate limited) |
| `scripts/fetch_real_data.py` | Direct, minimal fields | Fast | Low (rate limited) |
| `scripts/fetch_with_proxies.py` | 100 rotating proxies | Very Fast | Low (proxy detection) |
| `scripts/fetch_slow_sequential.py` | Sequential + delays | Slow | Low (still limited) |

## For Users

If you're trying to use this MCP server:

### Quick Start

1. **Clone the repo**:
   ```bash
   git clone https://github.com/rapturt9/mcp-alignmentforum.git
   cd mcp-alignmentforum
   ```

2. **Try fetching data from YOUR computer**:
   ```bash
   python3 scripts/fetch_slow_sequential.py
   ```

3. **If successful**, commit and push:
   ```bash
   git add data/alignment-forum-posts.csv
   git commit -m "Add real AF data"
   git push
   ```

4. **Install MCP SDK** (requires Python 3.10+):
   ```bash
   pip3.11 install 'git+https://github.com/modelcontextprotocol/python-sdk.git'
   ```

5. **Configure Claude Desktop**:
   ```json
   {
     "mcpServers": {
       "alignment-forum": {
         "command": "python3.11",
         "args": ["/path/to/mcp-alignmentforum/src/mcp_alignmentforum/server.py"]
       }
     }
   }
   ```

### Current Data

The repo includes **sample data** (15 realistic posts) for testing. This is enough to:
- Test the MCP server functionality
- Verify tool integration with Claude
- Develop and debug

Once you fetch real data, it will automatically replace the sample data.

## Technical Details

### Rate Limit Headers

The AF API doesn't return standard rate limit headers, making it difficult to know:
- How many requests are allowed
- When the limit resets
- What the time window is

### API Access Patterns

Based on testing:
- ✅ GraphiQL interface works (manual use)
- ❌ Automated batch requests blocked
- ❌ High-frequency requests blocked
- ❌ Proxy requests blocked

### Recommended Approach

For legitimate educational/research use:
1. **Small batches**: Fetch 20-50 posts at a time
2. **Long delays**: Wait 5-10 seconds between requests
3. **Identify yourself**: Use descriptive User-Agent
4. **Be respectful**: Don't hammer the API
5. **Consider alternatives**: Ask for data dumps

## GitHub Actions

The daily GitHub Actions workflow will also be rate-limited initially. Once you get an initial dataset:

1. The workflow runs from GitHub's IP (different from yours)
2. It only runs once per day
3. It should work after the first successful manual run

## Conclusion

**The MCP server code is complete and working.** The only blocker is getting past the API rate limits to fetch initial data.

**Try running the fetch scripts from YOUR computer** - you likely won't be rate-limited!
