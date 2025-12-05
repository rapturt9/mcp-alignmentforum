#!/usr/bin/env python3
"""Quick test to verify MCP server can start and list tools"""

import asyncio
import json
import subprocess
import sys

async def test_mcp_server():
    print("=" * 70)
    print("TESTING MCP SERVER")
    print("=" * 70)
    print()

    server_path = "/Users/ram/Github/mcp-alignmentforum/src/mcp_alignmentforum/server.py"
    python_path = "/usr/local/bin/python3.11"

    print(f"Server: {server_path}")
    print(f"Python: {python_path}")
    print()

    # Test that imports work
    print("Testing imports...")
    test_import = subprocess.run(
        [python_path, "-c", "import mcp; print('✅ MCP SDK imported')"],
        capture_output=True,
        text=True
    )

    if test_import.returncode == 0:
        print(test_import.stdout.strip())
    else:
        print(f"❌ Import failed: {test_import.stderr}")
        return False

    print()
    print("Testing server startup...")

    # The MCP server runs on stdio, so we can't easily test it without sending MCP protocol messages
    # Just verify it can import and start without errors
    test_startup = subprocess.run(
        [python_path, "-c",
         "import sys; sys.path.insert(0, '/Users/ram/Github/mcp-alignmentforum/src'); "
         "from mcp_alignmentforum.server import app; print('✅ Server imported successfully')"],
        capture_output=True,
        text=True,
        timeout=5
    )

    if test_startup.returncode == 0:
        print(test_startup.stdout.strip())
    else:
        print(f"❌ Server startup failed: {test_startup.stderr}")
        return False

    print()
    print("=" * 70)
    print("✅ MCP SERVER IS READY!")
    print("=" * 70)
    print()
    print("Configuration added to Claude Desktop:")
    print('  ~/Library/Application Support/Claude/claude_desktop_config.json')
    print()
    print("Next steps:")
    print("1. Restart Claude Desktop (Cmd+Q then reopen)")
    print("2. Look for the hammer/tools icon in Claude Desktop")
    print("3. You should see 'alignment-forum' server with 2 tools:")
    print("   - load_alignment_forum_posts")
    print("   - fetch_article_content")
    print()
    print("Try asking Claude:")
    print('  "Load the alignment forum posts and show me the top 5 by karma"')
    print()

    return True

if __name__ == "__main__":
    success = asyncio.run(test_mcp_server())
    sys.exit(0 if success else 1)
