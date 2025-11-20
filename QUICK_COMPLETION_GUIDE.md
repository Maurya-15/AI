# Quick Completion Guide - Copy & Paste Code

This guide provides ready-to-use code for completing the remaining critical tasks.

## Task 12: Scheduler Service (CRITICAL)

### File: `backend/app/scheduler.py`

```python
"""Campaign scheduler for daily outreach."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from typing import Optional
import logging

from app.config import get_settings
from app.db import get_db_context
from app.models import Lead, Campaign, OutreachHistory
from app.outreach.personalizer import EmailPersonalizer
from app.outreach.emailer import EmailSender, OutreachEmail
from app.audit import get_audit_logger

logger = logging.getLogger(__name__)


class CampaignScheduler:
    """Scheduler for daily email and call campaigns."""
    
    def __init__(self):
        """Initialize scheduler."""
        self.scheduler = AsyncIOScheduler()
        self.settings = get_settings()
        self.personalizer = EmailPersonalizer()
        self.emailer = EmailSender()
        self.audit = get_audit_logger()
    
    def start(self):
        """Start the scheduler."""
        # Email campaign at configured time (default 10:00 IST)
        hour, minute = map(int, self.settings.EMAIL_SEND_TIME.split(':'))
        self.scheduler.add_job(
            self.execute_email_campaign,
            CronTrigger(hour=hour, minute=minute, timezone=self.settings.TIMEZONE),
            id='daily_email_campaign'
        )
        
        logger.info(f"Scheduled email campaign for {self.settings.EMAIL_SEND_TIME} {self.settings.TIMEZONE}")
        self.scheduler.start()
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
    
    async def execute_email_campaign(self):
        """Execute daily email campaign."""
        logger.info("Starting daily email campaign")
        
        try:
            with get_db_context() as db:
                # Create campaign record
                campaign = Campaign(
                    campaign_type="email",
                    started_at=datetime.utcnow()
                )
                db.add(campaign)
                db.commit()
                db.refresh(campaign)
                
                # Get eligible leads
                cooldown_date = datetime.utcnow() - timedelta(days=self.settings.COOLDOWN_DAYS)
                
                leads = db.query(Lead).filter(
                    Lead.email_verified == True,
                    Lead.opted_out == False,
                    Lead.primary_email != None,
                    (Lead.last_contacted_at == None) | (Lead.last_contacted_at < cooldown_date)
                ).limit(self.settings.DAILY_EMAIL_CAP).all()
                
                logger.info(f"Found {len(leads)} eligible leads")
                
                success_count = 0
                fail_count = 0
                
                for lead in leads:
                    try:
                        # Generate personalized content
                        email_content = await self.personalizer.generate(lead)
                        
                        # Create outreach email
                        outreach = OutreachEmail(
                            lead_id=lead.id,
                            to_email=lead.primary_email,
                            subject=email_content.subject,
                            body_html=email_content.body_html,
                            body_text=email_content.body_text,
                            unsubscribe_token=self.emailer.generate_unsubscribe_token(lead.id, lead.primary_email)
                        )
                        
                        # Send email
                        result = await self.emailer.send(outreach)
                        
                        # Record outreach
                        outreach_record = OutreachHistory(
                            lead_id=lead.id,
                            campaign_id=campaign.id,
                            outreach_type="email",
                            content_hash=self.emailer.calculate_content_hash(email_content.body_text),
                            status="sent" if result.success else "failed",
                            provider_message_id=result.message_id,
                            provider_response=result.provider_response,
                            attempted_at=result.sent_at
                        )
                        db.add(outreach_record)
                        
                        # Update lead
                        if result.success:
                            lead.last_contacted_at = datetime.utcnow()
                            lead.contact_count += 1
                            success_count += 1
                        else:
                            fail_count += 1
                        
                        db.commit()
                        
                    except Exception as e:
                        logger.error(f"Failed to process lead {lead.id}: {e}")
                        fail_count += 1
                        continue
                
                # Update campaign
                campaign.total_attempted = len(leads)
                campaign.total_success = success_count
                campaign.total_failed = fail_count
                campaign.completed_at = datetime.utcnow()
                db.commit()
                
                # Log campaign completion
                await self.audit.log_campaign(
                    campaign_id=campaign.id,
                    campaign_type="email",
                    action="complete",
                    details={
                        "total_attempted": len(leads),
                        "total_success": success_count,
                        "total_failed": fail_count
                    }
                )
                
                logger.info(f"Campaign complete: {success_count} sent, {fail_count} failed")
        
        except Exception as e:
            logger.error(f"Campaign execution failed: {e}")
            await self.audit.log_error("scheduler", e, {"action": "execute_email_campaign"})


# Global scheduler instance
_scheduler: Optional[CampaignScheduler] = None


def get_scheduler() -> CampaignScheduler:
    """Get global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = CampaignScheduler()
    return _scheduler


# For running as standalone service
if __name__ == "__main__":
    import asyncio
    
    scheduler = get_scheduler()
    scheduler.start()
    
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.stop()
```

### Update `backend/app/main.py` to start scheduler:

```python
# Add at the top
from app.scheduler import get_scheduler

# Add to startup_event
@app.on_event("startup")
async def startup_event():
    # ... existing code ...
    
    # Start scheduler
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

# Add to shutdown_event
@app.on_event("shutdown")
async def shutdown_event():
    # ... existing code ...
    
    # Stop scheduler
    scheduler = get_scheduler()
    scheduler.stop()
    logger.info("Scheduler stopped")
```

## Task 15: FastAPI Endpoints (CRITICAL)

### Add to `backend/app/main.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db import get_db
from app.models import (
    Lead, LeadResponse, LeadCreate, LeadUpdate,
    OutreachHistory, OutreachHistoryResponse,
    OptOut, OptOutResponse,
    Campaign, CampaignResponse,
    ApprovalQueue, ApprovalQueueResponse
)
from app.opt_out import get_opt_out_manager

# Create API router
api_router = APIRouter(prefix="/api/v1", tags=["api"])

# Lead endpoints
@api_router.get("/leads", response_model=List[LeadResponse])
async def get_leads(
    skip: int = 0,
    limit: int = 100,
    verified_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get list of leads."""
    query = db.query(Lead)
    
    if verified_only:
        query = query.filter(Lead.email_verified == True, Lead.phone_verified == True)
    
    leads = query.offset(skip).limit(limit).all()
    return leads


@api_router.post("/leads", response_model=LeadResponse)
async def create_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    """Create a new lead."""
    db_lead = Lead(**lead.dict())
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return db_lead


@api_router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: int, db: Session = Depends(get_db)):
    """Get a specific lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@api_router.patch("/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: int, lead_update: LeadUpdate, db: Session = Depends(get_db)):
    """Update a lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    for key, value in lead_update.dict(exclude_unset=True).items():
        setattr(lead, key, value)
    
    db.commit()
    db.refresh(lead)
    return lead


# Outreach history endpoints
@api_router.get("/outreach-history", response_model=List[OutreachHistoryResponse])
async def get_outreach_history(
    skip: int = 0,
    limit: int = 100,
    lead_id: Optional[int] = None,
    outreach_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get outreach history."""
    query = db.query(OutreachHistory)
    
    if lead_id:
        query = query.filter(OutreachHistory.lead_id == lead_id)
    if outreach_type:
        query = query.filter(OutreachHistory.outreach_type == outreach_type)
    
    history = query.order_by(OutreachHistory.attempted_at.desc()).offset(skip).limit(limit).all()
    return history


# Campaign endpoints
@api_router.get("/campaigns", response_model=List[CampaignResponse])
async def get_campaigns(
    skip: int = 0,
    limit: int = 20,
    campaign_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get campaigns."""
    query = db.query(Campaign)
    
    if campaign_type:
        query = query.filter(Campaign.campaign_type == campaign_type)
    
    campaigns = query.order_by(Campaign.started_at.desc()).offset(skip).limit(limit).all()
    return campaigns


@api_router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Get a specific campaign."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


# Approval queue endpoints
@api_router.get("/approval-queue", response_model=List[ApprovalQueueResponse])
async def get_approval_queue(
    skip: int = 0,
    limit: int = 50,
    status: str = "pending",
    db: Session = Depends(get_db)
):
    """Get approval queue items."""
    items = db.query(ApprovalQueue).filter(
        ApprovalQueue.status == status
    ).order_by(ApprovalQueue.created_at.desc()).offset(skip).limit(limit).all()
    return items


@api_router.post("/approval-queue/{item_id}/approve")
async def approve_item(
    item_id: int,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """Approve a queued item."""
    item = db.query(ApprovalQueue).filter(ApprovalQueue.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item.status = "approved"
    item.reviewed_by = user_id
    item.reviewed_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "message": "Item approved"}


@api_router.post("/approval-queue/{item_id}/reject")
async def reject_item(
    item_id: int,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """Reject a queued item."""
    item = db.query(ApprovalQueue).filter(ApprovalQueue.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item.status = "rejected"
    item.reviewed_by = user_id
    item.reviewed_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "message": "Item rejected"}


# Opt-out endpoints
@api_router.get("/opt-outs", response_model=List[OptOutResponse])
async def get_opt_outs(
    skip: int = 0,
    limit: int = 100,
    contact_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get opt-out list."""
    query = db.query(OptOut)
    
    if contact_type:
        query = query.filter(OptOut.contact_type == contact_type)
    
    opt_outs = query.order_by(OptOut.opted_out_at.desc()).offset(skip).limit(limit).all()
    return opt_outs


@api_router.post("/unsubscribe")
async def unsubscribe(token: str = Query(...)):
    """Process unsubscribe request."""
    manager = get_opt_out_manager()
    success = await manager.process_unsubscribe_link(token)
    
    if success:
        return {"success": True, "message": "You have been unsubscribed"}
    else:
        raise HTTPException(status_code=400, detail="Failed to process unsubscribe")


# Statistics endpoint
@api_router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get system statistics."""
    total_leads = db.query(Lead).count()
    verified_leads = db.query(Lead).filter(
        Lead.email_verified == True,
        Lead.phone_verified == True
    ).count()
    opted_out = db.query(Lead).filter(Lead.opted_out == True).count()
    
    today = datetime.utcnow().date()
    emails_today = db.query(OutreachHistory).filter(
        OutreachHistory.outreach_type == "email",
        OutreachHistory.attempted_at >= today
    ).count()
    
    calls_today = db.query(OutreachHistory).filter(
        OutreachHistory.outreach_type == "call",
        OutreachHistory.attempted_at >= today
    ).count()
    
    return {
        "total_leads": total_leads,
        "verified_leads": verified_leads,
        "opted_out": opted_out,
        "emails_sent_today": emails_today,
        "calls_made_today": calls_today,
        "email_cap": get_settings().DAILY_EMAIL_CAP,
        "call_cap": get_settings().DAILY_CALL_CAP
    }


# Include router in app
app.include_router(api_router)
```

## Testing the Implementation

### 1. Test Scheduler

```bash
# Run scheduler standalone
python -m app.scheduler
```

### 2. Test API Endpoints

```bash
# Start API
uvicorn app.main:app --reload

# Test endpoints
curl http://localhost:8000/api/v1/stats
curl http://localhost:8000/api/v1/leads?limit=10
curl http://localhost:8000/api/v1/campaigns
```

### 3. Test Full Flow

```python
# backend/scripts/test_flow.py
import asyncio
from app.scheduler import get_scheduler

async def test_campaign():
    scheduler = get_scheduler()
    await scheduler.execute_email_campaign()

if __name__ == "__main__":
    asyncio.run(test_campaign())
```

## Quick Deploy to Production

### 1. Set Environment Variables

```bash
# Required
export DATABASE_URL="postgresql://..."
export EMAIL_FROM="marketing@yourdomain.com"
export BUSINESS_ADDRESS="Your Address"
export SENDGRID_API_KEY="SG...."
export OPENAI_API_KEY="sk-..."

# Disable dry-run (after testing!)
export DRY_RUN_MODE=false
export APPROVAL_MODE=true
```

### 2. Run with Docker

```bash
docker-compose up -d
```

### 3. Monitor

```bash
# View logs
docker-compose logs -f backend

# Check stats
curl http://localhost:8000/api/v1/stats
```

## Done! 🎉

You now have:
- ✅ Automated daily campaigns
- ✅ REST API for dashboard
- ✅ Complete outreach system
- ✅ Full compliance features

Next: Build the React dashboard or use the API directly!
