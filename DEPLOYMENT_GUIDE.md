# AI Research Assistant - Deployment Guide
## Railway (Backend) + Vercel/Netlify (Frontend)

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Security Setup](#security-setup)
3. [Backend Deployment (Railway)](#backend-deployment-railway)
4. [Frontend Deployment (Vercel/Next.js)](#frontend-deployment-vercelnextjs)
5. [Testing & Verification](#testing--verification)
6. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│   Vercel / Netlify (Frontend)               │
│   - Next.js / Tailwind CSS                  │
│   - React-based streaming UI                │
│   - Modern Authentication Flows             │
└──────────────────┬──────────────────────────┘
                   │ HTTP/REST API calls
                   │ (NEXT_PUBLIC_API_URL)
                   ▼
┌─────────────────────────────────────────────┐
│   Railway.app (Backend)                     │
│   - FastAPI server (api/routes.py)         │
│   - LangGraph research agents (Gemini)      │
│   - PostgreSQL + ChromaDB                   │
└─────────────────────────────────────────────┘
```

**Key Points:**
- Backend and Frontend are **separate deployments**.
- Frontend communicates with backend via `NEXT_PUBLIC_API_URL`.
- Each service can be scaled/restarted independently.

---

## Security Setup (CRITICAL ⚠️)

### Step 1: Secure Your API Keys
Ensure your `.env` file is never committed to Git.

### Step 2: Environment Variables
Keep these locally for development:
```
GEMINI_API_KEY=your-gemini-key
TAVILY_API_KEY=your-tavily-key
MODEL_NAME=gemini-1.5-flash
HOST=0.0.0.0
PORT=8000
```

---

## Backend Deployment (Railway)

### Step 1: Create Railway Project
1. Go to [Railway.app](https://railway.app).
2. Connect your GitHub repository.
3. Railway will automatically detect the Python environment.

### Step 2: Set Variables
In the Railway Dashboard, set:
- `GEMINI_API_KEY`
- `TAVILY_API_KEY`
- `MODEL_NAME`
- `PORT` (usually 8000)

---

## Frontend Deployment (Vercel/Next.js)

### Step 1: Prepare Frontend
1. Go to [Vercel](https://vercel.com).
2. Select the `frontend` directory in your repository.
3. Vercel will detect Next.js automatically.

### Step 2: Set Frontend Variables
Add the following environment variable in Vercel:
- `NEXT_PUBLIC_API_URL`: Your Railway Public URL (e.g., `https://project-name.up.railway.app`)

---

## Testing & Verification

### Test 1: Backend Health Check
```bash
curl https://your-railway-url/health
```

### Test 2: Research Stream
Ensure your frontend can receive NDJSON streams from the `/research/stream` endpoint.

---

## Troubleshooting
- **CORS Errors**: Ensure `api/routes.py` allows your Vercel domain.
- **API Timeout**: Gemini responses can take 10-30s; ensure your frontend fetch timeout is high enough.
- **Model Errors**: Verify `MODEL_NAME` matches a valid Google Generative AI model (e.g., `gemini-1.5-flash`).
