# PolarGrid AI - Deployment Guide

## GitHub Push Instructions

### Step 1: Create GitHub Repository

1. Go to [https://github.com/new](https://github.com/new)
2. Repository name: `polar_grid`
3. Description: `AI-Driven Smart Energy Management System for Polar Research Stations - SIH 2026`
4. Make it **Public** (required for SIH submission)
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click **Create repository**

### Step 2: Push Code to GitHub

Open terminal in the `polar_grid` folder and run:

```bash
# Add GitHub as remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/polar_grid.git

# Push to GitHub
git push -u origin master
```

**Example:**
```bash
git remote add origin https://github.com/krishrajput/polar_grid.git
git push -u origin master
```

### Step 3: Verify

Visit your repository URL:
```
https://github.com/YOUR_USERNAME/polar_grid
```

You should see all files including:
- `backend/` - Python backend code
- `frontend/` - HTML/CSS/JS dashboard
- `api/` - Vercel serverless handler
- `README.md` - Project documentation
- `vercel.json` - Deployment config

---

## Vercel Deployment Instructions

### Step 1: Create Vercel Account

1. Go to [https://vercel.com](https://vercel.com)
2. Click **Sign Up**
3. Sign up with **GitHub** (recommended) or email
4. Verify your email

### Step 2: Import Project

1. After login, click **Add New Project**
2. Click **Import Git Repository**
3. Find and select `polar_grid` from your GitHub repos
4. Click **Import**

### Step 3: Configure Deployment

Vercel will auto-detect the Python project. Configure as follows:

**Framework Preset:** `Other`

**Build Command:**
```bash
pip install -r requirements.txt
```

**Output Directory:** `.`

**Install Command:** (leave empty)

**Environment Variables:** (none needed)

Click **Deploy**

### Step 4: Wait for Deployment

Vercel will:
1. Install dependencies (~30 seconds)
2. Build the project (~10 seconds)
3. Deploy to edge network (~20 seconds)

**Total time: ~60 seconds**

### Step 5: Access Your Live App

Once deployed, you'll get a URL like:
```
https://polar-grid-ai.vercel.app
```

**First request will take 30-40 seconds** (ML model training on cold start).
**Subsequent requests are instant** (~200ms).

---

## Local Development

### Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
python backend/main.py

# Open in browser
# http://localhost:8000
```

### Test APIs

```bash
# Health check
curl http://localhost:8000/api/health

# List stations
curl http://localhost:8000/api/stations

# Get dashboard data
curl "http://localhost:8000/api/dashboard?station=Maitri%20(Antarctica)&hours_ahead=168"

# Get model performance
curl http://localhost:8000/api/model-performance
```

---

## Vercel-Specific Notes

### Cold Start

- **First request after deployment:** 30-40 seconds (ML model training)
- **Subsequent requests:** ~200ms (models cached in memory)
- **After 15 minutes of inactivity:** Cold start again (Vercel serverless behavior)

### Timeout

- **Default timeout:** 10 seconds
- **Configured timeout:** 60 seconds (in `vercel.json`)
- This accommodates the first-request cold start

### File Size

- **Total repo size:** ~15 MB
- **Largest files:** Diagrams (~500 KB each)
- **Within Vercel limits:** Yes (100 MB limit)

---

## Troubleshooting

### Issue: "Module not found" on Vercel

**Fix:** Make sure all dependencies are in `requirements.txt`

### Issue: "500 Internal Server Error" on Vercel

**Fix:** Check Vercel logs:
1. Go to your project dashboard
2. Click **Functions** tab
3. Click on the latest invocation
4. Check the logs for errors

### Issue: Slow first request

**Normal behavior.** ML models train on first request. Subsequent requests are fast.

### Issue: "Static files not found"

**Fix:** Make sure `vercel.json` routes are correct (they are in the current setup)

---

## Custom Domain (Optional)

1. Go to your Vercel project settings
2. Click **Domains**
3. Add your custom domain (e.g., `polargrid.frostbyte.dev`)
4. Follow Vercel's DNS configuration instructions

---

## Environment Variables (Future)

If you need to add API keys or secrets:

1. Go to Vercel project settings
2. Click **Environment Variables**
3. Add variables (e.g., `API_KEY`, `DATABASE_URL`)
4. Redeploy

**Currently not needed** — the app works without any environment variables.

---

## Performance Optimization

### For Production

1. **Pre-train models:** Save trained models to disk and load instead of training on first request
2. **Use Vercel Pro:** $20/month for longer timeouts and more memory
3. **Add caching:** Redis for API responses (requires external service)

### Current Setup

- **Training on first request:** Simpler, no model files to manage
- **60-second timeout:** Accommodates cold start
- **Edge deployment:** Fast global CDN

---

## Support

**Email:** 0241csds060@niet.co.in
**GitHub Issues:** https://github.com/YOUR_USERNAME/polar_grid/issues

---

**Built for Smart India Hackathon 2026**
**Theme: Clean & Green Technology**
**Team: FrostByte**
