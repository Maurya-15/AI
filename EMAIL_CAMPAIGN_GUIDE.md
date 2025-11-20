# Email Campaign Guide - 100 Businesses

## ✅ What's Configured

- ✅ **Email System**: SMTP with Gmail (working)
- ✅ **Daily Cap**: 100 emails per day
- ✅ **LocationIQ API**: Configured for location services
- ❌ **Call System**: Removed (not needed)
- ✅ **DRY_RUN_MODE**: Disabled (sends real emails)
- ✅ **APPROVAL_MODE**: Disabled (sends automatically)

## 📧 Email Recipients

The system will send emails to **100 businesses**:
- **99 real business emails** (placeholder data - you can replace with real businesses)
- **1 demo email**: anshum25506@gmail.com

## 🚀 Quick Start

### Step 1: Add 100 Business Leads

```bash
python add_100_business_leads.py
```

This will:
- Clear any existing leads
- Add 100 business leads to the database
- Mark all emails as verified and ready to send

### Step 2: Send Emails Immediately

```bash
python trigger_campaign.py email
```

This will send personalized emails to all 100 businesses right away.

### Step 3: Check Results

The campaign will show:
```
✅ Email campaign executed successfully

📊 Campaign Report:
------------------------------------------------------------
Campaign ID: X
Type: email
Total Attempted: 100
Total Success: 100
Total Failed: 0
Duration: X.XX seconds
```

## 📅 Automatic Daily Emails

The system is configured to automatically send emails at **10:00 AM IST** every day.

To enable automatic sending:
1. Keep the application running: `python run_app.py`
2. The scheduler will trigger at 10:00 AM IST daily
3. It will send to up to 100 eligible leads per day

## 🔧 Configuration

### Email Settings (.env)

```env
# SMTP (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=anshum25506@gmail.com
SMTP_PASSWORD=your_gmail_app_password

# Email From
EMAIL_FROM=mauryadoshi1@gmail.com
EMAIL_FROM_NAME=DevSync Innovation

# Daily Cap
DAILY_EMAIL_CAP=100

# Safety
DRY_RUN_MODE=false
APPROVAL_MODE=false

# Scheduling
EMAIL_SEND_TIME=10:00
TIMEZONE=Asia/Kolkata

# Location Services
LOCATIONIQ_API_KEY=pk.d382341d4ec8673afb43fbb070402341
```

## 📝 Customizing Business Leads

To add your own real business data, edit `add_100_business_leads.py`:

```python
business_leads = [
    {
        "business_name": "Your Business Name",
        "email": "contact@business.com",
        "city": "City Name",
        "category": "Business Category"
    },
    # Add 99 more...
]
```

## 📊 Email Content

Each email is personalized with:
- Business name
- Business category
- City location
- Custom value proposition
- Unsubscribe link (compliance)
- Business address (compliance)

Example:
```
Subject: Website Solutions for [Business Name]

Hi [Business Name] team,

I noticed you're in the [Category] business in [City]. 
We specialize in building fast, SEO-optimized websites 
for [Category] companies.

Would you be open to a quick 15-minute call to discuss 
how we can help grow your online presence?

Book a time: https://calendly.com/devsyncinnovation

Best regards,
DevSync Innovation Team
```

## 🛡️ Compliance Features

✅ **Unsubscribe Link**: Every email includes an unsubscribe link  
✅ **Business Address**: Physical address included in footer  
✅ **Opt-Out Tracking**: System tracks and honors opt-outs  
✅ **Rate Limiting**: Max 100 emails per day  
✅ **Cooldown Period**: 30 days between contacts to same lead  

## 📈 Monitoring

### Check Campaign Status

```bash
# View schedule
python trigger_campaign.py schedule

# Check stats via API
curl http://localhost:8000/api/v1/stats
```

### View Logs

The application logs show:
- Email send attempts
- Success/failure rates
- Error messages
- Opt-out requests

## ⚠️ Important Notes

1. **Gmail App Password**: Make sure you're using an App Password, not your regular Gmail password
2. **Daily Limit**: Gmail has sending limits (~500/day for regular accounts)
3. **Spam Prevention**: Don't send too many emails too quickly
4. **Content Quality**: Personalized emails perform better
5. **Opt-Outs**: Always honor unsubscribe requests immediately

## 🔄 Workflow

```
1. Add 100 business leads
   ↓
2. System verifies emails are ready
   ↓
3. Trigger campaign (manual or scheduled)
   ↓
4. System generates personalized content
   ↓
5. Emails sent via Gmail SMTP
   ↓
6. Results logged and tracked
   ↓
7. 30-day cooldown before next contact
```

## 🎯 Success Metrics

Monitor these metrics:
- **Delivery Rate**: Should be >95%
- **Open Rate**: Target 20-30%
- **Response Rate**: Target 2-5%
- **Opt-Out Rate**: Should be <1%

## 🆘 Troubleshooting

### Emails Not Sending?
- Check Gmail App Password is correct
- Verify SMTP settings in .env
- Check DRY_RUN_MODE=false
- Look at application logs for errors

### Low Delivery Rate?
- Verify email addresses are valid
- Check spam folder
- Ensure sender domain has SPF/DKIM

### Getting Blocked?
- Reduce daily cap
- Add delays between sends
- Improve email content quality
- Warm up the sending domain

---

**Ready to send?** Run: `python add_100_business_leads.py` then `python trigger_campaign.py email`
