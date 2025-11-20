# DevSyncSalesAI Demo Guide

## ✅ Current Status

Your demo contact has been added to the database:
- **Email**: anshum25506@gmail.com
- **Phone**: +917698895249
- **Status**: Verified and ready for outreach

## 🎯 Testing Modes

### 1. DRY-RUN Mode (Current - SAFE)
- **Status**: ✅ ENABLED
- **Behavior**: Simulates campaigns without sending real emails/calls
- **Perfect for**: Testing the system flow and logic
- **Current campaigns work in this mode**

### 2. PRODUCTION Mode (Real Outreach)
- **Status**: ❌ DISABLED
- **Behavior**: Sends real emails and makes real calls
- **Requires**: Valid API keys and proper configuration

## 🚀 How to Run Campaigns

### Option 1: Manual Trigger (Recommended for Testing)

```bash
# Trigger email campaign
python trigger_campaign.py email

# Trigger call campaign
python trigger_campaign.py call

# Trigger both campaigns
python trigger_campaign.py both

# Check campaign schedule
python trigger_campaign.py schedule
```

### Option 2: Via API

```bash
# Email campaign
curl -X POST http://localhost:8000/api/v1/campaigns/trigger/email

# Call campaign
curl -X POST http://localhost:8000/api/v1/campaigns/trigger/call
```

### Option 3: Scheduled (Automatic)

The system automatically runs campaigns at:
- **Email Campaign**: 10:00 AM IST (daily)
- **Call Campaign**: 11:00 AM IST (daily, Monday-Friday only)

## 📧 To Send REAL Emails

### Step 1: Verify SendGrid Configuration

Check your `.env` file:
```env
SENDGRID_API_KEY=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
EMAIL_FROM=devsyncinnovation@gmail.com
EMAIL_FROM_NAME=DevSync Innovation
```

### Step 2: Disable DRY_RUN Mode

Edit `.env`:
```env
DRY_RUN_MODE=false
```

### Step 3: Restart Application

```bash
# Stop the current process (Ctrl+C if running)
# Then restart:
python run_app.py
```

### Step 4: Trigger Email Campaign

```bash
python trigger_campaign.py email
```

**Expected Result**: Real email will be sent to anshum25506@gmail.com

## 📞 To Make REAL Calls

### Step 1: Verify Twilio Configuration

Check your `.env` file:
```env
TWILIO_ACCOUNT_SID=AC4d27d3ef5d2e10795723c5141ac5c068
TWILIO_AUTH_TOKEN=aecfe717adec4d3333cd1e66b3e454b2
TWILIO_PHONE_NUMBER=+919876543210
```

### Step 2: Ensure Call Window

Calls only work:
- **Time**: 11:00 AM - 5:00 PM IST
- **Days**: Monday - Friday

### Step 3: Disable DRY_RUN Mode

Edit `.env`:
```env
DRY_RUN_MODE=false
```

### Step 4: Restart Application

```bash
python run_app.py
```

### Step 5: Trigger Call Campaign

```bash
python trigger_campaign.py call
```

**Expected Result**: Real call will be made to +917698895249

## ⚠️ Important Safety Notes

### Before Going Live:

1. **Test with DRY_RUN=true first** ✅
2. **Verify all API keys are valid**
3. **Check email authentication** (SPF, DKIM, DMARC)
4. **Confirm Twilio phone number is verified**
5. **Review compliance requirements** (CAN-SPAM, TRAI, GDPR)
6. **Start with low daily caps** (already set to 100)
7. **Keep APPROVAL_MODE=true initially**

### Current Safety Settings:

```env
DRY_RUN_MODE=true          # ✅ Safe - no real outreach
APPROVAL_MODE=true         # ✅ Requires approval before sending
DAILY_EMAIL_CAP=100        # ✅ Limited daily sends
DAILY_CALL_CAP=100         # ✅ Limited daily calls
COOLDOWN_DAYS=30           # ✅ 30-day cooldown between contacts
```

## 📊 Monitoring Campaigns

### View Campaign Reports

```bash
# Check API stats
curl http://localhost:8000/api/v1/stats

# View campaign schedule
python trigger_campaign.py schedule
```

### Check Database

```bash
# View all leads
python -c "from backend.app.db import *; from backend.app.models import *; init_db(); db = next(get_db()); print(db.query(Lead).all())"
```

### View Logs

The application logs show:
- Campaign execution
- Email/call attempts
- Success/failure rates
- Error messages

## 🎬 Demo Workflow

### Safe Demo (DRY-RUN Mode):

1. **Start Application**:
   ```bash
   python run_app.py
   ```

2. **Trigger Email Campaign**:
   ```bash
   python trigger_campaign.py email
   ```
   - Shows: "Would send email to anshum25506@gmail.com"
   - No actual email sent

3. **Trigger Call Campaign**:
   ```bash
   python trigger_campaign.py call
   ```
   - Shows: "Would call +917698895249"
   - No actual call made

### Live Demo (PRODUCTION Mode):

1. **Update .env**:
   ```env
   DRY_RUN_MODE=false
   ```

2. **Restart Application**:
   ```bash
   python run_app.py
   ```

3. **Trigger Email Campaign**:
   ```bash
   python trigger_campaign.py email
   ```
   - ✉️ Real email sent to anshum25506@gmail.com
   - Check inbox for personalized email

4. **Trigger Call Campaign** (during call window):
   ```bash
   python trigger_campaign.py call
   ```
   - 📞 Real call made to +917698895249
   - Answer to hear AI voice message

## 🔧 Troubleshooting

### Email Not Sending?

1. Check SendGrid API key is valid
2. Verify EMAIL_FROM domain is authenticated
3. Check logs for error messages
4. Ensure DRY_RUN_MODE=false

### Call Not Working?

1. Check Twilio credentials are valid
2. Verify phone number is in E.164 format (+917698895249)
3. Ensure within call window (11 AM - 5 PM IST, Mon-Fri)
4. Check DRY_RUN_MODE=false
5. Verify Twilio phone number is active

### Campaign Shows 0 Leads?

1. Check leads are verified: `email_verified=True` and `phone_verified=True`
2. Ensure leads are not opted out: `opted_out=False`
3. Check cooldown period hasn't been triggered
4. Run: `python add_demo_contact.py` to re-add demo contact

## 📝 Next Steps

1. ✅ Test in DRY-RUN mode (completed)
2. ⏭️ Verify API credentials
3. ⏭️ Test real email send
4. ⏭️ Test real call (during call window)
5. ⏭️ Add more leads
6. ⏭️ Monitor campaign performance
7. ⏭️ Adjust daily caps based on results

## 🎉 Success Indicators

### Email Campaign Success:
- ✅ Campaign report shows "total_success": 1
- ✅ Email appears in anshum25506@gmail.com inbox
- ✅ Email includes unsubscribe link
- ✅ Email is personalized with business details

### Call Campaign Success:
- ✅ Campaign report shows "total_success": 1
- ✅ Phone +917698895249 receives call
- ✅ AI voice message plays
- ✅ Call is recorded in database

---

**Ready to test?** Start with DRY-RUN mode, then switch to PRODUCTION when you're confident!
