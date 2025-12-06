# Railway Deployment Guide

## ✅ Deployment Files Created

I've added all the necessary files for Railway deployment:

1. **Procfile** - Tells Railway how to start the server
2. **railway.json** - Railway configuration (build and deploy settings)
3. **Dockerfile** - Container configuration for reproducible builds
4. **.dockerignore** - Optimizes Docker builds by excluding unnecessary files
5. **server_remote.py** - SSE-based server for remote access (vs stdio for local)
6. **Updated pyproject.toml** - Added `uvicorn` and `starlette` dependencies

## 🚀 What Railway Will Do Now

Railway is connected to your GitHub repo and will automatically:

1. **Detect the push** - Saw your commit `fb8a3d9`
2. **Trigger new build** - Using Dockerfile and pyproject.toml
3. **Install dependencies** - Including the new uvicorn and starlette
4. **Build container** - Using Python 3.11
5. **Deploy** - Start server with SSE transport on assigned port
6. **Assign URL** - Give you a public HTTPS URL

## 📊 Check Deployment Status

Go to your Railway dashboard: https://railway.app/dashboard

You should see:
- **Build in progress** - Installing dependencies and building Docker image
- **Deployment logs** - Real-time logs showing startup
- **Success** - When it shows "Deployment successful"

## 🔗 Get Your Deployment URL

Once deployed:

1. Click on your Railway project
2. Go to **Settings** → **Networking**
3. Copy your **Public Domain** (e.g., `mcp-alignmentforum-production.up.railway.app`)

## 🔧 Configure Claude Desktop for Remote Server

Once you have the Railway URL, update your Claude Desktop config:

**File**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "alignment-forum-remote": {
      "url": "https://YOUR-APP-NAME.up.railway.app/sse",
      "transport": "sse"
    }
  }
}
```

Replace `YOUR-APP-NAME` with your actual Railway domain.

## 🧪 Test the Remote Server

Once deployed, test the SSE endpoint:

```bash
curl https://YOUR-APP-NAME.up.railway.app/sse
```

You should see SSE connection established.

## 📝 Key Differences: Local vs Remote

**Local (stdio):**
- Runs on your computer
- Uses Claude Desktop config with `uv` command
- Data flows through stdin/stdout
- Fast, no network latency

**Remote (SSE):**
- Runs on Railway servers
- Uses Claude Desktop config with URL
- Data flows through HTTPS/SSE
- Accessible from anywhere (Claude.ai, mobile, etc.)
- Slightly higher latency

## 🐛 Troubleshooting

### Build Still Failing?

Check Railway logs:
1. Go to Railway dashboard
2. Click on your project
3. Check **Deployments** tab
4. View latest deployment logs

Common issues:
- **Missing dependencies**: Should be fixed now with uvicorn/starlette added
- **Wrong Python version**: Dockerfile specifies Python 3.11
- **Port binding**: Fixed with `--host 0.0.0.0 --port $PORT`

### Can't Access /sse Endpoint?

1. Check Railway assigned a public URL in Settings → Networking
2. Make sure deployment shows as "Active"
3. Test with curl: `curl -v https://your-url.railway.app/sse`

### Server Not Responding?

Check the logs for errors:
- `ImportError`: Missing dependency (should be fixed)
- `Port already in use`: Railway auto-assigns ports
- `Connection refused`: Check firewall/networking settings

## 💰 Railway Pricing

- **Free tier**: $5 credit/month
- **Usage**: ~$0.10/hour for small apps
- **This server**: Should use minimal resources (mostly idle)

## 🔄 Auto-Deploy

Every time you push to GitHub main branch:
- Railway automatically rebuilds
- Deploys new version
- Zero downtime deployment
- Rollback available if needed

## 📚 Additional Resources

- [Railway Docs](https://docs.railway.app/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [Server Code](src/mcp_alignmentforum/server_remote.py)
- [Main README](README.md)

---

**Current Status**: All files pushed to GitHub (commit `fb8a3d9`)
**Next Step**: Check Railway dashboard for deployment status!
