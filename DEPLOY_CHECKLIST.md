# Render Deployment Checklist

## ✅ Pre-Deployment

- [x] Fixed requirements.txt (removed python-mailgun)
- [x] Removed calling functionality
- [x] Configured email system (SMTP)
- [x] Added LocationIQ API key
- [x] Set daily cap to 100 emails
- [x] Scheduler configured for 10:00 AM IST

## 🚀 Deployment Steps

### 1. Push to GitHub
```bash
git add .
git commit -m "Fixed requirements for Render deployment"
git push origin main
```

### 2. Create Render Services

**PostgreSQL Database:**
- Name: `devsync-sales-db`
- Plan: Free
- Copy Internal Database URL

**Web Service:**
- Name: `devsync-sales-ai`
- Environment: Python 3
- Build: `pip install -r requirements.txt`
- Start: `python run_app.py`
- Plan: Free (or $7/month for 24/7)

### 3. Environment Variables (Copy-Paste Ready)

```env
DATABASE_URL=<paste_your_postgres_internal_url>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=anshum25506@gmail.com
SMTP_PASSWORD=<your_gmail_app_password>
EMAIL_FROM=mauryadoshi1@gmail.com
EMAIL_FROM_NAME=DevSync Innovation
BUSINESS_ADDRESS=123 Tech Park, Bangalore, Karnataka 560001, India
LOCATIONIQ_API_KEY=pk.d382341d4ec8673afb43fbb070402341
DAILY_EMAIL_CAP=100
COOLDOWN_DAYS=30
APPROVAL_MODE=false
DRY_RUN_MODE=false
TIMEZONE=Asia/Kolkata
EMAIL_SEND_TIME=10:00
PER_DOMAIN_EMAIL_LIMIT=5
EMAIL_VERIFICATION_CONFIDENCE_THRESHOLD=0.7
LOG_LEVEL=INFO
```

### 4. Deploy & Verify

Check logs for:
```
✅ Campaign scheduler started
✅ Scheduled daily email campaign at 10:00 Asia/Kolkata
```

### 5. Add Business Leads

You'll need to add 100 business leads to the database after deployment.

### 6. Test

```bash
curl -X POST https://your-app.onrender.com/api/v1/campaigns/trigger/email
```

## ⚠️ Important

**Free Tier Limitation:**
- App sleeps after 15 min inactivity
- Scheduler may not work reliably
- **Recommendation**: Upgrade to $7/month for 24/7 uptime

## 🎯 Success Criteria

- [ ] App deployed without errors
- [ ] Scheduler started successfully
- [ ] Test email sent successfully
- [ ] Email received at anshum25506@gmail.com
- [ ] Logs show no errors

---

**Ready to deploy!** The requirements.txt is now fixed. Try deploying again on Render.
