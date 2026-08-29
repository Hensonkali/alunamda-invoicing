# ALUNAMDA Invoicing - Render Deployment Guide

## Quick Deploy (5 minutes)

### Step 1: Create Render Account
1. Go to https://render.com
2. Sign up with GitHub (free)

### Step 2: Push to GitHub
```bash
cd "C:\Users\LENOVO T14\Desktop\Projects\Alunamda\alunamda-cloud"
git init
git add .
git commit -m "ALUNAMDA Invoicing for Render"
git remote add origin https://github.com/YOUR_USERNAME/alunamda-invoicing.git
git push -u origin main
```

### Step 3: Create Web Service
1. Go to https://dashboard.render.com
2. Click **New +** → **Web Service**
3. Connect your GitHub repo
4. Configure:
   - **Name:** alunamda-invoicing
   - **Runtime:** Docker
   - **Plan:** Free
   - **Region:** Europe (Frankfurt) - closest to South Africa
   - **Disk:** 1 GB (for SQLite database)

### Step 4: Add Environment Variables
In Render dashboard, go to **Environment** tab and add:
```
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
CSRF_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
APP_NAME=ALUNAMDA Invoicing
DEBUG=false
SESSION_EXPIRE_MINUTES=1440
ITEMS_PER_PAGE=25
ACTIVITY_PER_PAGE=50
DATA_DIR=/data
```

### Step 5: Deploy
Click **Create Web Service** → Render will build and deploy automatically.

### Step 6: Login
- URL: https://alunamda-invoicing.onrender.com
- Email: admin@alunamda.co.za
- Password: Admin@123

## Files Created
- `render.yaml` - Render Blueprint config
- `Dockerfile` - Updated for Render (port from $PORT env)
- `DEPLOY_RENDER.md` - This guide

## Notes
- **Free tier** includes 750 hours/month (auto-sleeps after 15 min idle)
- **Persistent disk** keeps your SQLite database safe
- **Auto-HTTPS** included
- **Logs** available in Render dashboard

## Troubleshooting
- If build fails, check logs in Render dashboard
- Ensure disk is attached to the service
- Verify environment variables are set correctly
