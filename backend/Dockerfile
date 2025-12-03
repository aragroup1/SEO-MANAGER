# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p /app/screenshots /app/temp

# Add the command to run your app
CMD ["python", "main.py"]
```

Make sure there are NO ``` backticks anywhere in the file!

## 2. Yes, You Need Multiple Services!

For a proper full-stack setup, you should have **FIVE services** in Railway:

### Current Setup (Wrong):
- 1 GitHub repo service (trying to run everything)
- PostgreSQL
- Redis

### Correct Setup (What you need):
1. **Backend API Service** (Python/FastAPI) - Root: `/backend`
2. **Frontend Service** (Next.js) - Root: `/frontend` 
3. **PostgreSQL Database**
4. **Redis** (optional for caching)
5. **Worker Service** (optional for background jobs)

## 3. How to Set Up Multiple Services from One Repo

In Railway, you can create multiple services from the same GitHub repo:

### Step 1: Create Backend Service
1. Click **"New"** → **"GitHub Repo"**
2. Select your repo
3. In Settings:
   - **Root Directory**: `/backend`
   - **Start Command**: (will use Dockerfile CMD)
4. Add environment variable:
   - `DATABASE_URL`: Connect to PostgreSQL service

### Step 2: Create Frontend Service
1. Click **"New"** → **"GitHub Repo"** (same repo)
2. Select your repo again
3. In Settings:
   - **Root Directory**: `/frontend`
   - **Start Command**: `npm run start`
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL`: Your backend service URL (e.g., `https://your-backend.railway.app`)

### Step 3: Connect Services
In Railway, click and drag between services to connect them:
- Backend → PostgreSQL (for DATABASE_URL)
- Backend → Redis (for REDIS_URL)

## 4. Quick Setup Commands

For your backend service environment variables:
```
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
PORT=8000
```

For your frontend service environment variables:
```
NEXT_PUBLIC_API_URL=https://[your-backend-service].railway.app
PORT=8080
