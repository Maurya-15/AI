# Deployment Checklist

## Pre-Deployment (Testing Phase)

### Configuration
- [ ] Copy `.env.example` to `.env`
- [ ] Set `DATABASE_URL` to your PostgreSQL instance
- [ ] Set `EMAIL_FROM` to your sending email
- [ ] Set `BUSINESS_ADDRESS` to your physical address
- [ ] Configure at least one email provider (SendGrid recommended)
- [ ] Configure email verification provider (AbstractAPI)
- [ ] Configure phone verification provider (NumVerify)
- [ ] Configure AI provider (OpenAI)
- [ ] Keep `DRY_RUN_MODE=true`
- [ ] Keep `APPROVAL_MODE=true`
- [ ] Set `DAILY_EMAIL_CAP=10` (low for testing)

### Database Setup
- [ ] PostgreSQL 14+ installed and running
- [ ] Database created
- [ ] Run: `python -c "from app.db import init_db; init_db()"`
- [ ] Seed test data: `python backend/scripts/seed_leads.py`
- [ ] Verify tables created: Check database

### Testing
- [ ] Run all tests: `bash run_tests.sh`
- [ ] All tests passing (85 tests)
- [ ] No errors in test output
- [ ] Coverage report generated

### Dry-Run Testing
- [ ] Start API: `uvicorn app.main:app --reload`
- [ ] Check health: `curl http://localhost:8000/health`
- [ ] Check stats: `curl http://localhost:8000/api/v1/stats`
- [ ] Run test campaign: `python backend/scripts/run_once.py`
- [ ] Review logs for "DRY-RUN" messages
- [ ] Verify no actual emails sent
- [ ] Check database for outreach records

## Email Authentication Setup

### SPF Record
- [ ] Add SPF record to DNS:
  ```
  v=spf1 include:sendgrid.net ~all
  ```
- [ ] Verify SPF: Use MXToolbox or similar

### DKIM
- [ ] Follow SendGrid/Mailgun DKIM setup instructions
- [ ] Add DKIM records to DNS
- [ ] Verify DKIM: Send test email, check headers

### DMARC
- [ ] Add DMARC record to DNS:
  ```
  v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
  ```
- [ ] Verify DMARC: Use DMARC analyzer

### Domain Verification
- [ ] Verify sending domain with email provider
- [ ] Send test email to yourself
- [ ] Check email headers for authentication
- [ ] Verify email doesn't go to spam

## Production Deployment

### Environment Configuration
- [ ] Review all environment variables
- [ ] Set production `DATABASE_URL`
- [ ] Verify all API keys are production keys
- [ ] Set `DRY_RUN_MODE=false` (⚠️ ONLY AFTER TESTING)
- [ ] Keep `APPROVAL_MODE=true` initially
- [ ] Set `DAILY_EMAIL_CAP=100` (or lower)
- [ ] Set `DAILY_CALL_CAP=100` (or lower)
- [ ] Configure `SENTRY_DSN` for error tracking (optional)

### Deployment Method

#### Option 1: Docker Compose
- [ ] Update `docker-compose.yml` with production settings
- [ ] Run: `docker-compose up -d`
- [ ] Check logs: `docker-compose logs -f`
- [ ] Verify all services running: `docker-compose ps`

#### Option 2: Render.com
- [ ] Push code to GitHub
- [ ] Create Render account
- [ ] Import `infra/render.yaml`
- [ ] Configure environment variables in Render dashboard
- [ ] Deploy services
- [ ] Check service logs in Render dashboard

### Post-Deployment Verification
- [ ] API accessible: `curl https://your-domain.com/health`
- [ ] Database connected: Check health endpoint
- [ ] Scheduler running: Check logs for "Scheduler started"
- [ ] No errors in logs

## Going Live

### Initial Live Campaign
- [ ] Set `DRY_RUN_MODE=false` in production environment
- [ ] Keep `APPROVAL_MODE=true`
- [ ] Set low daily cap (10-20 emails)
- [ ] Monitor first campaign closely
- [ ] Check opt-out rate (should be < 2%)
- [ ] Check bounce rate (should be < 5%)
- [ ] Review email deliverability

### Gradual Scale-Up
- [ ] Week 1: 10-20 emails/day
- [ ] Week 2: 30-50 emails/day (if metrics good)
- [ ] Week 3: 50-100 emails/day (if metrics good)
- [ ] Monitor metrics at each stage
- [ ] Adjust messaging based on feedback

### Monitoring Setup
- [ ] Set up daily log review
- [ ] Configure alerts for errors
- [ ] Monitor opt-out rate daily
- [ ] Track response rates
- [ ] Review campaign reports

## Compliance Verification

### Legal Requirements
- [ ] Physical address in all emails ✅
- [ ] Unsubscribe link in all emails ✅
- [ ] Opt-out honored immediately ✅
- [ ] Only public business contacts ✅
- [ ] Privacy policy accessible
- [ ] Terms of service available
- [ ] Legal counsel review (recommended)

### Operational Compliance
- [ ] Operator trained on compliance requirements
- [ ] Opt-out process documented
- [ ] Escalation procedure defined
- [ ] Regular compliance audits scheduled

## Security Checklist

### Application Security
- [ ] API keys in environment variables ✅
- [ ] Sensitive data masked in logs ✅
- [ ] Database connections encrypted
- [ ] HTTPS/TLS enabled (in production)
- [ ] Dashboard authentication configured
- [ ] API rate limiting enabled
- [ ] Input validation active ✅

### Operational Security
- [ ] API keys rotated quarterly
- [ ] Access logs reviewed
- [ ] Backup strategy defined
- [ ] Disaster recovery plan documented
- [ ] Security incident response plan

## Maintenance Schedule

### Daily
- [ ] Review campaign statistics
- [ ] Check opt-out requests
- [ ] Monitor error logs
- [ ] Verify system health

### Weekly
- [ ] Review response rates
- [ ] Analyze bounce rates
- [ ] Check provider status
- [ ] Review messaging effectiveness

### Monthly
- [ ] Rotate API keys
- [ ] Review compliance
- [ ] Analyze campaign performance
- [ ] Update documentation
- [ ] Security audit

### Quarterly
- [ ] Full system audit
- [ ] Legal compliance review
- [ ] Performance optimization
- [ ] Feature planning

## Emergency Procedures

### Stop All Outreach
```bash
# Method 1: Stop services
docker-compose down

# Method 2: Set caps to 0
export DAILY_EMAIL_CAP=0
export DAILY_CALL_CAP=0
docker-compose restart
```

### Process Urgent Opt-out
```python
from app.opt_out import get_opt_out_manager
import asyncio

async def urgent_opt_out():
    manager = get_opt_out_manager()
    await manager.add_opt_out("email", "urgent@example.com", "manual")

asyncio.run(urgent_opt_out())
```

### Rollback Deployment
```bash
# Docker
docker-compose down
git checkout previous-version
docker-compose up -d

# Render
# Use Render dashboard to rollback to previous deployment
```

## Success Criteria

### System Health
- ✅ All tests passing
- ✅ No errors in logs
- ✅ API responding < 200ms
- ✅ Database queries < 100ms
- ✅ Scheduler executing on time

### Campaign Performance
- ✅ Opt-out rate < 2%
- ✅ Bounce rate < 5%
- ✅ Delivery rate > 95%
- ✅ Response rate > 1%
- ✅ No spam complaints

### Compliance
- ✅ All opt-outs honored
- ✅ Unsubscribe links working
- ✅ Email authentication passing
- ✅ Audit logs complete
- ✅ No legal complaints

## Sign-Off

### Pre-Production
- [ ] Technical lead approval
- [ ] Compliance officer approval
- [ ] Security review complete
- [ ] Documentation reviewed

### Production
- [ ] Deployment successful
- [ ] All checks passing
- [ ] Monitoring active
- [ ] Team trained

---

**Deployment Date**: _____________

**Deployed By**: _____________

**Approved By**: _____________

**Status**: ⬜ Testing | ⬜ Staging | ⬜ Production

---

**Use this checklist to ensure safe, compliant deployment of DevSyncSalesAI.**
