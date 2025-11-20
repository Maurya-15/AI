# Render Deployment Guide

## 🚀 Quick Deploy to Render

### Step 1: Push to GitHub

```bash
git add .
git commit -m "Ready for Render deployment"
git push origin main
```

### Step 2: Create Render Web Service

1. Go to https://dashboard.render.com/
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `devsync-sales-ai`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python run_app.py`
   - **Instance Type**: Free (or paid for 24/7)

### Step 3: Add PostgreSQL Database

1. In Render Dashboard, click **"New +"** → **"PostgreSQL"**
2. Name it: `devsync-sales-db`
3. Choose **Free** tier
4. Click **"Create Database"**
5. Copy the **Internal Database URL**

### Step 4: Set Environment Variables

In your Web Service settings, add these environment variables:

```env
# Database (from PostgreSQL you just created)
DATABASE_URL=<paste_internal_database_url_here>

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=anshum25506@gmail.com
SMTP_PASSWORD=<your_gmail_app_password>
EMAIL_FROM=mauryadoshi1@gmail.com
EMAIL_FROM_NAME=DevSync Innovation
BUSINESS_ADDRESS=123 Tech Park, Bangalore, Karnataka 560001, India

# Email Verification (optional)
ABSTRACTAPI_KEY=62598a0e8d4c43e0a27b3c8f8da0fb7c
ZEROBOUNCE_API_KEY=24c3a03c42c54a8197ec210c84144be1

# Location Services
LOCATIONIQ_API_KEY=pk.d382341d4ec8673afb43fbb070402341

# AI Services (optional - for personalization)
OPENAI_API_KEY=<your_openai_key_if_you_have_one>

# Operational Settings
DAILY_EMAIL_CAP=100
COOLDOWN_DAYS=30
APPROVAL_MODE=false
DRY_RUN_MODE=false
TIMEZONE=Asia/Kolkata
EMAIL_SEND_TIME=10:00

# Rate Limiting
PER_DOMAIN_EMAIL_LIMIT=5
EMAIL_VERIFICATION_CONFIDENCE_THRESHOLD=0.7
PHONE_VERIFICATION_CONFIDENCE_THRESHOLD=0.6

# Logging
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=90
```

### Step 5: Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your repo
   - Install dependencies
   - Start the application
   - Start the scheduler

### Step 6: Add Business Leads

After deployment, you need to add your 100 business leads to the database.

**Option 1: Via API (Recommended)**

Create a script to add leads via API:

```python
import requests

url = "https://your-app.onrender.com/api/v1/leads"

# Add your 100 business leads
for lead in business_leads:
    response = requests.post(url, json=lead)
    print(f"Added: {lead['business_name']}")
```

**Option 2: Via Database Migration**

Create an Alembic migration with seed data.

### Step 7: Verify Scheduler

Check the logs in Render dashboard:

```
✅ Campaign scheduler started
✅ Scheduled daily email campaign at 10:00 Asia/Kolkata
```

### Step 8: Test Email Campaign

Trigger manually via API:

```bash
curl -X POST https://your-app.onrender.com/api/v1/campaigns/trigger/email
```

## 📊 Monitoring

### Check Application Status

```bash
curl https://your-app.onrender.com/health
```

### View Campaign Stats

```bash
curl https://your-app.onrender.com/api/v1/stats
```

### Check Schedule

```bash
curl https://your-app.onrender.com/api/v1/campaigns/schedule
```

## ⚠️ Important Notes

### Free Tier Limitations

- **Sleeps after 15 minutes of inactivity**
- **Wakes up on incoming requests**
- **Scheduler may not work reliably on free tier**

**Solution**: Upgrade to paid plan ($7/month) for 24/7 uptime

### Keep Service Alive (Free Tier Workaround)

Use a cron job service to ping your app every 10 minutes:

```bash
# Use cron-job.org or similar
curl https://your-app.onrender.com/health
```

### Database Backups

Render Free PostgreSQL:
- **Limited to 1GB**
- **No automatic backups**
- **Deleted after 90 days of inactivity**

**Solution**: Upgrade to paid database for backups

## 🔧 Troubleshooting

### Build Fails

Check logs for missing dependencies:
```bash
pip install -r requirements.txt
```

### Scheduler Not Running

Check environment variables:
- `EMAIL_SEND_TIME=10:00`
- `TIMEZONE=Asia/Kolkata`

### Emails Not Sending

1. Verify Gmail App Password is correct
2. Check `DRY_RUN_MODE=false`
3. Check `APPROVAL_MODE=false`
4. View logs for errors

### Database Connection Issues

1. Verify `DATABASE_URL` is set correctly
2. Use **Internal Database URL** (not External)
3. Check PostgreSQL is running

## 📅 Scheduler Behavior on Render

### How It Works

1. **App Starts** → Scheduler starts automatically
2. **Waits for 10:00 AM IST** → Checks time every second
3. **At 10:00 AM IST** → Triggers email campaign
4. **Sends to 100 businesses** → Up to daily cap
5. **Next Day** → Repeats automatically

### Time Zone Handling

- Render servers run on **UTC**
- Scheduler converts to **Asia/Kolkata (IST)**
- 10:00 AM IST = 4:30 AM UTC

### Reliability

- ✅ **Paid Plan**: 100% reliable, runs 24/7
- ⚠️ **Free Plan**: May sleep, scheduler may miss scheduled time

## 🎯 Post-Deployment Checklist

- [ ] Application deployed successfully
- [ ] PostgreSQL database created and connected
- [ ] All environment variables set
- [ ] 100 business leads added to database
- [ ] Scheduler shows in logs as started
- [ ] Test email sent successfully
- [ ] Verified emails arrive at anshum25506@gmail.com
- [ ] Checked logs for errors
- [ ] Set up monitoring/alerts (optional)

## 🚀 You're Live!

Your application will now:
- ✅ Run 24/7 on Render
- ✅ Send emails automatically at 10:00 AM IST daily
- ✅ Track all campaigns and results
- ✅ Honor opt-outs and compliance rules

**API Endpoint**: `https://your-app.onrender.com`  
**API Docs**: `https://your-app.onrender.com/docs`  
**Health Check**: `https://your-app.onrender.com/health`

---

**Need help?** Check Render docs: https://render.com/docs
