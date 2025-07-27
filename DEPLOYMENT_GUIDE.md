# Railway Deployment Guide

## Step 1: Prepare for Railway
1. Create account at https://railway.app
2. Install Railway CLI: `npm install -g @railway/cli`
3. Login: `railway login`

## Step 2: Deploy Database
1. In Railway dashboard, click "New Project"
2. Select "PostgreSQL" 
3. Note the connection details provided

## Step 3: Update Environment Variables
Update your .env file with Railway database credentials:
```
DB_NAME=railway
DB_USER=postgres
DB_PASSWORD=<provided_password>
DB_HOST=<provided_host>
DB_PORT=<provided_port>
```

## Step 4: Deploy Backend
1. Run: `railway init`
2. Run: `railway up`
3. Railway will give you a public URL like: https://your-app.railway.app

## Step 5: Update Frontend
Replace all `192.168.118.164:5000` with your Railway URL in:
- queue-number.html
- queue-status.html
