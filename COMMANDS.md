# DevSyncSalesAI - Commands Guide

## 📧 Email Campaign Commands

### 1. Send Emails NOW (Immediate)

```bash
python send_now.py
```

**What it does:**
- Sends emails immediately to all eligible businesses
- No waiting for scheduled time
- Shows real-time progress and results
- Perfect for testing or urgent campaigns

**Example Output:**
```
📧 DevSyncSalesAI - Send Emails NOW
====================================================================
🔧 Initializing...
📤 Email From: mauryadoshi1@gmail.com
📧 Daily Cap: 100
🔒 DRY_RUN_MODE: False

🚀 Starting email campaign...
--------------------------------------------------------------------

====================================================================
✅ Email Campaign Completed!
====================================================================
📊 Campaign ID: 15
📤 Total Attempted: 100
✅ Total Success: 100
❌ Total Failed: 0
⏱️  Duration: 2.45 seconds
====================================================================

🎉 Successfully sent 100 emails!
📬 Check inbox: anshum25506@gmail.com
```

---

### 2. Start Automatic Scheduler (Daily at 10:00 AM)

```bash
python start_scheduler.py
```

**What it does:**
- Starts the application with automatic scheduler
- Sends emails daily at 10:00 AM IST
- Runs continuously in the background
- Press Ctrl+C to stop

**Example Output:**
```
📅 DevSyncSalesAI - Automatic Email Scheduler
====================================================================

⏰ Scheduled Time: 10:00 Asia/Kolkata
📧 Daily Email Cap: 100
📤 Email From: mauryadoshi1@gmail.com

🔄 The scheduler will automatically send emails daily at the scheduled time.
   Press Ctrl+C to stop the scheduler.

====================================================================

INFO: Started server process
INFO: Waiting for application startup.
INFO: Scheduled daily email campaign at 10:00 Asia/Kolkata
INFO: Campaign scheduler started
```

---

## 🔧 Setup Commands

### Add 100 Business Leads

```bash
python add_100_business_leads.py
```

Adds 100 business leads to the database (99 placeholder + 1 real demo email).

---

### Quick Setup (All-in-One)

```bash
python setup_and_run.py
```

Runs the complete setup:
1. Adds 100 business leads
2. Shows you're ready to send

---

## 📊 Monitoring Commands

### Check Campaign Schedule

```bash
python trigger_campaign.py schedule
```

Shows when the next scheduled campaign will run.

---

### Check System Stats (API)

```bash
curl http://localhost:8000/api/v1/stats
```

Returns:
```json
{
  "total_leads": 100,
  "verified_leads": 100,
  "opted_out": 0,
  "emails_sent_today": 95,
  "email_cap": 100
}
```

---

## 🎯 Quick Reference

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `python send_now.py` | Send emails immediately | Testing, urgent campaigns |
| `python start_scheduler.py` | Start automatic daily sending | Production, hands-off operation |
| `python add_100_business_leads.py` | Add business leads | Initial setup, refresh leads |
| `python setup_and_run.py` | Complete setup | First time setup |

---

## 💡 Usage Examples

### Example 1: Send Emails Right Now

```bash
# Add leads
python add_100_business_leads.py

# Send immediately
python send_now.py
```

### Example 2: Set Up Automatic Daily Sending

```bash
# Add leads
python add_100_business_leads.py

# Start scheduler (runs forever)
python start_scheduler.py
```

### Example 3: Test Campaign

```bash
# Send to test
python send_now.py

# Check results
curl http://localhost:8000/api/v1/stats
```

---

## ⚙️ Configuration

Edit `.env` file to change settings:

```env
# Email settings
EMAIL_FROM=mauryadoshi1@gmail.com
DAILY_EMAIL_CAP=100

# Schedule (for automatic sending)
EMAIL_SEND_TIME=10:00
TIMEZONE=Asia/Kolkata

# Safety
DRY_RUN_MODE=false
APPROVAL_MODE=false
```

---

## 🛑 Stopping Commands

### Stop Immediate Send
- Press `Ctrl+C` during execution

### Stop Scheduler
- Press `Ctrl+C` in the terminal running `start_scheduler.py`

---

## 📝 Notes

- **send_now.py**: Executes once and exits
- **start_scheduler.py**: Runs continuously until stopped
- Both commands respect the daily email cap (100)
- Both commands honor opt-outs and cooldown periods
- Emails are personalized for each business

---

## 🆘 Troubleshooting

### Command not working?

1. Check Python is installed: `python --version`
2. Check you're in the project directory
3. Check `.env` file has correct settings
4. Check Gmail App Password is configured

### No emails sent?

1. Check `DRY_RUN_MODE=false` in `.env`
2. Verify leads exist: `python add_100_business_leads.py`
3. Check daily cap not reached
4. Look at logs for errors

---

**Ready to send?** Choose your command and go! 🚀
