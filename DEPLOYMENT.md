# Deployment Guide - Electric RAG

This guide covers deploying Electric RAG to Railway (recommended) or other platforms.

## Quick Deploy to Railway

### Prerequisites
- GitHub account with this repository pushed
- Railway account (https://railway.app)
- Google Gemini API key (https://aistudio.google.com/apikey)

### Step 1: Create Railway Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Connect your GitHub account and select this repository

### Step 2: Add PostgreSQL Database

1. In your Railway project, click **"+ New"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway automatically provides `DATABASE_URL` to your services

### Step 3: Deploy Backend Service

1. Click **"+ New"** → **"GitHub Repo"**
2. Select this repository
3. Set the **Root Directory** to `backend`
4. Add environment variables:
   ```
   GEMINI_API_KEY=your-gemini-api-key
   LLM_PROVIDER=gemini
   ENVIRONMENT=production
   DEBUG=false
   ```
5. Railway auto-detects the Dockerfile and deploys

### Step 4: Add Persistent Storage (Important!)

1. Click on your backend service
2. Go to **"Volumes"** tab
3. Add two volumes:
   - Mount path: `/app/uploads` (for PDF files)
   - Mount path: `/app/chroma_data` (for vector database)

### Step 5: Deploy Frontend Service

1. Click **"+ New"** → **"GitHub Repo"**
2. Select this repository again
3. Set the **Root Directory** to `frontend-vue`
4. Add build argument:
   ```
   VITE_API_URL=https://your-backend-service.railway.app
   ```
   (Get this URL from your backend service's Settings → Domains)

### Step 6: Configure Domains

1. Click on each service → **"Settings"** → **"Networking"**
2. Click **"Generate Domain"** for public access
3. Or add a custom domain

### Step 7: Verify Deployment

1. Visit your frontend URL
2. Check backend health: `https://your-backend.railway.app/health`
3. Upload a test document

---

## Environment Variables Reference

### Backend (Required)
| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Auto-provided by Railway |
| `GEMINI_API_KEY` | Google Gemini API key | `AIza...` |
| `LLM_PROVIDER` | LLM to use | `gemini` or `anthropic` |

### Backend (Optional)
| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Set to `production` |
| `DEBUG` | `true` | Set to `false` in production |
| `OCR_DPI` | `300` | OCR resolution |

### Frontend (Build-time)
| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API URL (must be set at build time) |

---

## Alternative: Deploy with Docker Compose

For VPS deployment (DigitalOcean, Linode, AWS EC2):

```bash
# 1. Clone repository
git clone https://github.com/your-username/Electric_RAG.git
cd Electric_RAG

# 2. Create .env file
cp .env.example .env
# Edit .env with your API keys

# 3. Build and run
docker-compose -f docker-compose.prod.yml up -d

# 4. Check status
docker-compose ps
```

---

## Estimated Costs

| Platform | Estimated Monthly Cost |
|----------|----------------------|
| Railway (Hobby) | $5-20 |
| Railway (Pro) | $20-50 |
| DigitalOcean Droplet | $12-24 |
| AWS (minimal) | $30-50 |

Railway Hobby plan includes:
- 512 MB RAM per service (upgrade if needed)
- 1 GB persistent storage
- Automatic SSL certificates
- GitHub integration

---

## Troubleshooting

### Backend won't start
- Check logs: Railway Dashboard → Service → Logs
- Verify `DATABASE_URL` is set (should be automatic with PostgreSQL addon)
- Ensure `GEMINI_API_KEY` is valid

### Frontend shows connection error
- Verify `VITE_API_URL` points to the correct backend URL
- Redeploy frontend after changing the URL (it's baked in at build time)
- Check backend is running: `curl https://your-backend.railway.app/health`

### Documents not persisting after redeploy
- Ensure volumes are attached to `/app/uploads` and `/app/chroma_data`
- Railway volumes persist across deploys

### Out of memory errors
- Backend needs ~2GB for embedding models
- Upgrade to Railway Pro or increase service memory

---

## CI/CD Pipeline

This project includes GitHub Actions workflows for continuous integration and deployment.

### CI Workflow (`.github/workflows/ci.yml`)

Runs automatically on every push and pull request:

| Job | Description |
|-----|-------------|
| **Backend CI** | Linting, type checking, pytest with PostgreSQL |
| **Frontend CI** | Linting, type checking, production build |
| **Docker Build** | Verifies Docker images build successfully |

### CD Workflow (`.github/workflows/deploy.yml`)

Runs on push to `main` branch after CI passes:

| Job | Description |
|-----|-------------|
| **Deploy to Railway** | Deploys backend and frontend via Railway CLI |
| **Push Images** | (Optional) Pushes to Docker Hub for self-hosted |

### Setting Up CI/CD

#### 1. GitHub Secrets (Required)

Go to your repo → Settings → Secrets and variables → Actions:

| Secret | Required | Description |
|--------|----------|-------------|
| `GEMINI_API_KEY` | Yes | For running tests |
| `RAILWAY_TOKEN` | Optional | For CLI deployments |
| `DOCKERHUB_USERNAME` | Optional | For pushing images |
| `DOCKERHUB_TOKEN` | Optional | For pushing images |

#### 2. Get Railway Token (Optional)

Railway auto-deploys via GitHub integration, but for CLI control:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and get token
railway login
railway whoami
```

Copy the token from `~/.railway/config.json` or generate one at:
Railway Dashboard → Account Settings → Tokens

#### 3. Enable Auto-Deploy in Railway

1. Go to Railway Dashboard → Your Project → Service
2. Settings → Source → Enable "Auto Deploy"
3. Select branch: `main`

Now every push to `main` triggers:
1. GitHub Actions CI (tests, lint, build)
2. Railway auto-deploy (if CI passes via branch protection)

### Branch Protection (Recommended)

To ensure CI passes before deploying:

1. GitHub repo → Settings → Branches → Add rule
2. Branch name pattern: `main`
3. Enable:
   - ✅ Require status checks to pass
   - ✅ Require branches to be up to date
4. Select required checks: `Backend CI`, `Frontend CI`, `Docker Build`

### Workflow Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Push to   │────▶│  GitHub     │────▶│  Railway    │
│   main      │     │  Actions CI │     │  Auto-Deploy│
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Tests Pass? │
                    └─────────────┘
                      │       │
                     Yes      No
                      │       │
                      ▼       ▼
                   Deploy   Block
```
