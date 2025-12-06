# Fix Railway Configuration

## The Problem

Railway is using an old cached configuration with:
```json
"startCommand": "uvicorn mcp_alignmentforum.server_remote:sse_app --host 0.0.0.0 --port $PORT"
```

This causes the error: `Invalid value for '--port': '$PORT' is not a valid integer`

## The Solution

You need to update Railway's settings manually since the railway.json file isn't overriding the existing configuration.

### Option 1: Update via Railway Dashboard (Easiest)

1. **Go to your Railway project**: https://railway.app/dashboard

2. **Click on your mcp-alignmentforum service**

3. **Go to Settings tab**

4. **Find "Start Command" or "Deploy" section**

5. **Change the start command to**:
   ```
   python -m mcp_alignmentforum
   ```

6. **Click "Save" or "Update"**

7. **Trigger a new deployment**:
   - Go to Deployments tab
   - Click "Redeploy" on the latest deployment
   OR
   - Make a small change and push to GitHub

### Option 2: Delete and Recreate (Clean Slate)

If updating settings doesn't work:

1. **Delete the current Railway service** (not the whole project, just the service)

2. **Create a new service from GitHub**:
   - Click "New Service"
   - Select "Deploy from GitHub repo"
   - Choose `mcp-alignmentforum`

3. **Railway will auto-detect** the Dockerfile and railway.json

4. **It should now use** the correct configuration

### Option 3: Use Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Update the start command
railway variables set START_COMMAND="python -m mcp_alignmentforum"

# Redeploy
railway up
```

## Verify It's Fixed

After updating, check the deployment logs. You should see:

```
Starting MCP server on 0.0.0.0:PORT_NUMBER
SSE endpoint: http://0.0.0.0:PORT_NUMBER/sse
```

Instead of the error about $PORT.

## Why This Happens

Railway stores configuration in their database separate from your railway.json file. When you created the service initially, it might have auto-detected settings that are now cached. The railway.json file should override this, but sometimes Railway's UI settings take precedence.

## Current Correct Configuration

Your repository now has:

**Dockerfile**:
```dockerfile
CMD ["python", "-m", "mcp_alignmentforum"]
```

**Procfile**:
```
web: python -m mcp_alignmentforum
```

**railway.json**:
```json
{
  "deploy": {
    "startCommand": "python -m mcp_alignmentforum",
    "healthcheckPath": "/sse"
  }
}
```

All of these properly read PORT from `os.environ.get("PORT", 8000)` without needing shell variable expansion.

## Next Steps

After fixing the Railway configuration, the deployment should succeed and you'll get a working HTTPS URL for your MCP server!
