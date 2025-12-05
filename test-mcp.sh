#!/bin/bash
# Test the MCP server using the MCP inspector

# Set PATH to include node and npm
export PATH=/usr/local/bin:$PATH

echo "Starting MCP Inspector for Alignment Forum server..."
echo ""
echo "This will open a web interface at http://localhost:5173"
echo "where you can test the MCP tools interactively."
echo ""

/usr/local/bin/npx @modelcontextprotocol/inspector \
  /usr/local/bin/uv \
  --directory /Users/ram/Github/mcp-alignmentforum \
  run \
  mcp-alignmentforum
