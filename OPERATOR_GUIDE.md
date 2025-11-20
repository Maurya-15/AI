# DevSyncSalesAI Operator Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Configuration](#configuration)
3. [Running the System](#running-the-system)
4. [Monitoring](#monitoring)
5. [Compliance](#compliance)
6. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- API keys for:
  - Email provider (SendGrid/Mailgun)
  - Email verification (AbstractAPI)
  - Phone verification (NumVerify/Twilio)
  - AI personalization (OpenAI)
  - Voice calls (Twilio) - optional

### Installation

```bash
# Clone repository
git clone <repository-url>
cd DevSyncSalesAI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

## Configuration

### Required Environment Variables

Edit `.env` file with your credentials:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/devsync_sales

# Email Provider (choose one)
SENDGRID_API_KEY=SG.your_key_here

# Email Configuration
EMAIL_FROM=marketing@yourdomain.com
EMAIL_FROM_NAME=Your Company Name
BUSINESS_ADDRESS=Your Physical Address Here

# Verification
ABSTRACTAPI_KEY=your_key_here
NUMVERIFY_KEY=your_key_here

# AI Personalization
OPENAI_API_KEY=sk-your_key_here

# Safety Settings (KEEP THESE FOR TESTING)
DRY_RUN_MODE=true
APPROVAL_MODE=true
DAILY_EMAIL_CAP=10
DAILY_CALL_CAP=10
```

### Email Domain Setup

**CRITICAL**: Configure email authentication before going live:

1. **SPF Record**: Add to your DNS:
   ```
   v=spf1 include:sendgrid.net ~all
   ```

2. **DKIM**: Follow your email provider's instructions

3. **DMARC**: Add to DNS:
   ```
   v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
   ```

## Running the System

### Development Mode

```bash
# Initialize database
python -c "from app.db import init_db; init_db()"

# Run API server
uvicorn app.main:app --reload

# Access API docs
open http://localhost:8000/docs
```

### Production Mode with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

### Testing Before Going Live

1. **Dry-Run Mode** (default):
   - Set `DRY_RUN_MODE=true`
   - System simulates all actions without sending
   - Review logs to verify behavior

2. **Test with Low Caps**:
   ```bash
   DAILY_EMAIL_CAP=5
   DAILY_CALL_CAP=5
   ```

3. **Run Test Campaign**:
   ```bash
   python -c "from app.scheduler import get_scheduler; import asyncio; asyncio.run(get_scheduler().execute_email_campaign())"
   ```

## Monitoring

### Check System Status

```bash
# API health check
curl http://localhost:8000/health

# Get statistics
curl http://localhost:8000/api/v1/stats
```

### View Logs

```bash
# All logs
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Scheduler only
docker-compose logs -f scheduler
```

### Key Metrics to Monitor

1. **Daily Caps**: Ensure not exceeding limits
2. **Opt-out Rate**: Should be < 2% (if higher, review messaging)
3. **Bounce Rate**: Should be < 5% (if higher, improve verification)
4. **Success Rate**: Should be > 90% (if lower, check provider)

### Database Queries

```sql
-- Check today's outreach
SELECT COUNT(*) FROM outreach_history 
WHERE attempted_at >= CURRENT_DATE;

-- Check opt-out rate
SELECT 
  (SELECT COUNT(*) FROM opt_outs) * 100.0 / 
  (SELECT COUNT(*) FROM leads) as opt_out_percentage;

-- Recent campaigns
SELECT * FROM campaigns 
ORDER BY started_at DESC LIMIT 10;
```

## Compliance

### Legal Requirements

#### CAN-SPAM (US)
- ✅ Include physical address in all emails
- ✅ Clear unsubscribe link
- ✅ Honor opt-outs within 10 days
- ✅ Accurate "From" information

#### TRAI (India)
- ✅ Only contact businesses with public info
- ✅ Respect Do Not Call registry
- ✅ Provide opt-out mechanism
- ✅ Call only during business hours (11 AM - 5 PM)

#### GDPR (EU)
- ✅ Store minimal data
- ✅ Provide data export on request
- ✅ Delete data on request
- ✅ Maintain opt-out records permanently

### Best Practices

1. **Start Small**: Begin with 10-20 emails/day
2. **Monitor Responses**: Track opt-out and response rates
3. **Quality Over Quantity**: Better targeting = better results
4. **Be Transparent**: Clear identity and purpose
5. **Honor Opt-outs Immediately**: Never contact opted-out leads

### Compliance Checklist

Before going live:
- [ ] Email domain authenticated (SPF/DKIM/DMARC)
- [ ] Physical address in all emails
- [ ] Unsubscribe link tested
- [ ] Opt-out enforcement verified
- [ ] Daily caps set appropriately
- [ ] Approval mode enabled for first campaign
- [ ] Privacy policy accessible
- [ ] Legal review completed

## Troubleshooting

### Common Issues

#### 1. Emails Not Sending

**Symptoms**: Emails stuck in queue or failing

**Solutions**:
- Check API key is valid
- Verify email domain authentication
- Check provider dashboard for issues
- Review logs for error messages

```bash
# Check email provider status
docker-compose logs backend | grep "email"
```

#### 2. High Bounce Rate

**Symptoms**: Many emails bouncing

**Solutions**:
- Increase verification confidence threshold
- Review lead sources
- Check email format validation

```python
# Adjust in .env
EMAIL_VERIFICATION_CONFIDENCE_THRESHOLD=0.8
```

#### 3. Database Connection Issues

**Symptoms**: "Connection refused" errors

**Solutions**:
```bash
# Check PostgreSQL is running
docker-compose ps db

# Restart database
docker-compose restart db

# Check connection string
echo $DATABASE_URL
```

#### 4. Scheduler Not Running

**Symptoms**: No campaigns executing

**Solutions**:
```bash
# Check scheduler logs
docker-compose logs scheduler

# Verify timezone
echo $TIMEZONE

# Manually trigger campaign
python -c "from app.scheduler import get_scheduler; import asyncio; asyncio.run(get_scheduler().execute_email_campaign())"
```

### Getting Help

1. **Check Logs**: Always start with logs
2. **Review Configuration**: Verify all required env vars set
3. **Test Components**: Test individual components
4. **Check Documentation**: Review design and requirements docs

### Emergency Procedures

#### Stop All Outreach Immediately

```bash
# Stop all services
docker-compose down

# Or set daily caps to 0
export DAILY_EMAIL_CAP=0
export DAILY_CALL_CAP=0
docker-compose restart
```

#### Process Mass Opt-out

```python
# Add multiple contacts to opt-out list
from app.opt_out import get_opt_out_manager
import asyncio

async def bulk_opt_out(emails):
    manager = get_opt_out_manager()
    for email in emails:
        await manager.add_opt_out("email", email, "manual")

# Run
asyncio.run(bulk_opt_out(["email1@example.com", "email2@example.com"]))
```

## Maintenance

### Daily Tasks
- Review campaign statistics
- Check opt-out requests
- Monitor error logs

### Weekly Tasks
- Review response rates
- Adjust messaging if needed
- Check system health metrics

### Monthly Tasks
- Rotate API keys
- Review compliance
- Analyze campaign performance
- Clean up old logs

## Support

For technical issues:
1. Check logs: `docker-compose logs -f`
2. Review documentation in `.kiro/specs/devsync-sales-ai/`
3. Run tests: `pytest`
4. Check configuration: Review `.env` file

---

**Remember**: You are responsible for legal compliance. Always prioritize ethical outreach and respect opt-out requests immediately.
