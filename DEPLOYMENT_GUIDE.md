# AI Research Assistant - Deployment Guide
## Railway (Backend) + Streamlit Cloud (Frontend)

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Security Setup](#security-setup)
3. [Backend Deployment (Railway)](#backend-deployment-railway)
4. [Frontend Deployment (Streamlit Cloud)](#frontend-deployment-streamlit-cloud)
5. [Testing & Verification](#testing--verification)
6. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│   Streamlit Cloud (Frontend)                │
│   - ui/app.py                              │
│   - Hosted on streamlit.io                 │
│   - Free tier                              │
└──────────────────┬──────────────────────────┘
                   │ HTTP/REST API calls
                   │ (API_URL environment variable)
                   ▼
┌─────────────────────────────────────────────┐
│   Railway.app (Backend)                     │
│   - FastAPI server (api/routes.py)         │
│   - LangGraph research agents              │
│   - ChromaDB for session memory            │
│   - Free tier (with limited resources)     │
└─────────────────────────────────────────────┘
```

**Key Points:**
- Backend and Frontend are **separate deployments**
- Frontend communicates with backend via `API_URL` environment variable
- Each service can be scaled/restarted independently

---

## Security Setup (CRITICAL ⚠️)

### Step 1: Secure Your API Keys

**Your `.env` file contains exposed API keys!** You must fix this immediately:

```powershell
# 1. Remove .env from git history
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch .env" --prune-empty --tag-name-filter cat -- --all

# 2. Add .env to .gitignore
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Add .env to gitignore"

# 3. Force push to GitHub
git push origin dev --force

# 4. Rotate your Gemini API key immediately
# Go to: https://console.cloud.google.com/apis/credentials
# Delete the old key and generate a new one
```

### Step 2: Update Your .env (for local development only)

Keep this file locally, NEVER commit it:

```
GEMINI_API_KEY=your-new-api-key-here
TAVILY_API_KEY=your-tavily-key
MODEL_NAME=gemini-2.5-flash
HOST=0.0.0.0
PORT=8000
RELOAD=false
MODE=api
```

---

## Backend Deployment (Railway)

### Step 1: Create Railway Account

1. Go to [Railway.app](https://railway.app)
2. Sign up with GitHub account
3. Create a new project

### Step 2: Create Railway Configuration Files

**File: `railway.toml`** (in root directory)

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python -m uvicorn api.routes:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "always"
restartPolicyMaxRetries = 3
```

**File: `.railway/nixpacks.toml`** (if needed)

```toml
[build]
usePoetry = false
nixpacks-version = "1.24.0"
```

### Step 3: Deploy to Railway

```bash
# 1. Install Railway CLI (if you haven't)
npm install -g @railway/cli

# 2. Login to Railway
railway login

# 3. Link your project
railway link

# 4. Add environment variables
railway variables set GEMINI_API_KEY="your-api-key"
railway variables set MODEL_NAME="gemini-2.5-flash"
railway variables set TAVILY_API_KEY="your-tavily-key"
railway variables set MODE="api"

# 5. Deploy
railway up
```

**Alternative: Deploy via Railway Dashboard**

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click "New Project" → "Deploy from GitHub"
3. Select your repository
4. In the Settings tab:
   - Set environment variables (see Step 3)
   - Make sure `python` is the runtime
5. Click "Deploy"

### Step 4: Get Your Backend URL

After deployment:
1. Go to Railway Dashboard
2. Click on your project
3. In the "Deployments" tab, copy the **Public URL**
4. It will look like: `https://your-project-random-id.railway.app`

**⚠️ Important:** Save this URL - you'll need it for Streamlit Cloud setup

---

## Frontend Deployment (Streamlit Cloud)

### Step 1: Prepare Your Repository

Ensure your GitHub repository has the correct structure:

```
project-root/
├── ui/
│   └── app.py          ← Streamlit app
├── api/
│   └── routes.py
├── config/
├── graph/
├── agents/
├── requirements.txt    ← Dependencies
├── .gitignore
├── main.py
└── DEPLOYMENT_GUIDE.md
```

### Step 2: Create Streamlit Configuration

**File: `.streamlit/config.toml`** (in root directory)

```toml
[client]
showErrorDetails = true
toolbarMode = "developer"

[logger]
level = "info"

[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

[server]
headless = true
port = 8501
enableXsrfProtection = true
```

### Step 3: Verify requirements.txt

Make sure all dependencies are in `requirements.txt`:

```bash
# Check if all imports are in requirements.txt
cat requirements.txt | grep -E "streamlit|requests|python-dotenv"

# Should see:
# streamlit==1.57.0
# requests==2.33.1
# python-dotenv==1.2.2
```

### Step 4: Deploy to Streamlit Cloud

1. Go to [Streamlit Cloud](https://streamlit.io/cloud)
2. Click "New app"
3. Select:
   - **Repository:** Your GitHub repo
   - **Branch:** `main` or `dev`
   - **Main file path:** `ui/app.py`
4. Click "Deploy"

### Step 5: Set Environment Variables in Streamlit Cloud

After deployment:

1. Click the **⋮ (three dots)** in the top right
2. Select "Settings"
3. Go to "Secrets" tab
4. Add the following (paste into the text area):

```toml
API_URL = "https://your-railway-backend-url"
```

Replace `your-railway-backend-url` with the URL from Railway deployment (Step 4 above)

---

## Testing & Verification

### Test 1: Backend Health Check

```bash
# Replace with your Railway URL
curl https://your-railway-url/health

# Should return 200 status
```

### Test 2: Backend API Endpoint

```bash
curl -X POST https://your-railway-url/research/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What is AI?", "session_id": "test-123"}' \
  --max-time 10

# Should start streaming responses
```

### Test 3: Streamlit Frontend

1. Go to your Streamlit Cloud URL (shown on dashboard)
2. Enter a research question
3. Click "Research"
4. Should see:
   - "Running: Memory (cache check)" → Progress
   - "Running: Supervisor" → Progress
   - Results with Quality Score

### Test 4: Connection Verification

Add this temporary debug code to `ui/app.py` (line 60, inside the `if research_button:` block):

```python
if st.checkbox("Debug Mode"):
    st.info(f"API Base URL: {API_BASE}")
    try:
        health = requests.get(f"{API_BASE}/health", timeout=2)
        st.success(f"✓ Backend Connected (Status: {health.status_code})")
    except Exception as e:
        st.error(f"✗ Cannot reach backend: {e}")
```

---

## Troubleshooting

### Issue 1: Frontend Can't Connect to Backend

**Error:** "Could not reach API at https://..."

**Solutions:**
1. Check the `API_URL` in Streamlit Cloud Secrets is correct
2. Verify Railway backend is running (check Railway dashboard)
3. Check Railway logs: `railway logs`
4. Ensure backend URL doesn't have trailing `/`

**Test:**
```bash
curl https://your-railway-url/health
```

### Issue 2: 502 Bad Gateway Error

**Solutions:**
1. Backend crashed - check Railway logs: `railway logs`
2. Backend out of memory - check Railway metrics
3. API key is invalid - verify `GEMINI_API_KEY` in Railway

**Check Railway Logs:**
```bash
railway logs -f  # -f for follow (live updates)
```

### Issue 3: Streamlit App Won't Load

**Solutions:**
1. Check Streamlit Cloud logs (click ⋮ → "Manage app" → "View logs")
2. Verify `requirements.txt` has all dependencies
3. Check `.streamlit/config.toml` is valid TOML

### Issue 4: Slow Response Times

**Reasons & Solutions:**
- Large dependency install on Railway free tier (wait 2-3 mins first time)
- LLM API slow (Gemini can take 10-30 seconds per response)
- Network latency (acceptable for free tier)

**Monitor:**
- Railway: Check dyno metrics (CPU, memory)
- Streamlit: Check browser DevTools → Network tab

### Issue 5: CORS Errors

**Error:** "Access to XMLHttpRequest blocked by CORS policy"

**Solution:** Add CORS middleware to `api/routes.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Environment Variables Summary

### Railway (Backend)

```
GEMINI_API_KEY=your-api-key
TAVILY_API_KEY=your-tavily-key
MODEL_NAME=gemini-2.5-flash
MODE=api
```

### Streamlit Cloud (Frontend)

```
API_URL=https://your-railway-backend-url
```

---

## Cost Breakdown

| Service | Plan | Cost/Month | Notes |
|---------|------|-----------|-------|
| **Railway** | Starter | $5-10 | Includes $5 free credit |
| **Streamlit Cloud** | Free | $0 | Unlimited free tier |
| **TOTAL** | - | **$5-10** | First month often free with credits |

✅ **This is your cheapest production-grade option**

---

## Next Steps

1. ✅ Secure your API keys (remove from git)
2. ✅ Create `railway.toml` file
3. ✅ Create `.streamlit/config.toml` file
4. ✅ Deploy to Railway
5. ✅ Deploy to Streamlit Cloud
6. ✅ Set `API_URL` in Streamlit Secrets
7. ✅ Test both services
8. ✅ Monitor logs if issues occur

---

## Quick Reference Commands

```bash
# Railway
railway login
railway link
railway variables set KEY=VALUE
railway up
railway logs -f

# Local Testing
export MODE=api
export API_URL=http://localhost:8000
python main.py

# Git
git push origin dev
```

---

## Support & Additional Resources

- **Railway Docs:** https://docs.railway.app
- **Streamlit Docs:** https://docs.streamlit.io
- **LangGraph Docs:** https://langchain-ai.github.io/langgraph

---

**Last Updated:** 2026-05-06
