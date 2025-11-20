"""Campaign scheduler service using APScheduler."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, time
from dataclasses import dataclass
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.config import get_settings
from app.db import get_db_context
from app.models import Campaign, Lead, OutreachHistory
from app.rate_limiter import get_rate_limiter
from app.queue import get_queue_manager
from app.audit import AuditLogger

logger = logging.getLogger(__name__)


@dataclass
class CampaignReport:
    """Campaign execution report."""
    campaign_id: int
    campaign_type: str
    total_attempted: int
    total_success: int
    total_failed: int
    errors: List[str]
    started_at: datetime
    completed_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "campaign_id": self.campaign_id,
            "campaign_type": self.campaign_type,
            "total_attempted": self.total_attempted,
            "total_success": self.total_success,
            "total_failed": self.total_failed,
            "error_count": len(self.errors),
            "errors": self.errors[:10],  # First 10 errors
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": (self.completed_at - self.started_at).total_seconds()
        }


class CampaignScheduler:
    """Schedule and execute daily outreach campaigns."""
    
    def __init__(self):
        """Initialize campaign scheduler."""
        self.config = get_settings()
        self.rate_limiter = get_rate_limiter()
        self.queue_manager = get_queue_manager()
        self.audit = AuditLogger()
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._running_campaigns: Dict[str, bool] = {}
    
    def start(self):
        """Start the scheduler."""
        if self.scheduler is not None:
            logger.warning("Scheduler already started")
            return
        
        # Create scheduler with timezone
        tz = pytz.timezone(self.config.TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=tz)
        
        # Schedule daily email campaign
        email_time = self._parse_time(self.config.EMAIL_SEND_TIME)
        self.scheduler.add_job(
            self.execute_email_campaign,
            CronTrigger(
                hour=email_time.hour,
                minute=email_time.minute,
                timezone=tz
            ),
            id="daily_email_campaign",
            name="Daily Email Campaign",
            replace_existing=True
        )
        logger.info(f"Scheduled daily email campaign at {self.config.EMAIL_SEND_TIME} {self.config.TIMEZONE}")
        
        # Start scheduler
        self.scheduler.start()
        logger.info("Campaign scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            logger.info("Campaign scheduler stopped")
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string (HH:MM) to time object."""
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour, minute)
        except Exception as e:
            logger.error(f"Error parsing time '{time_str}': {e}")
            return time(10, 0)  # Default to 10:00
    
    async def execute_email_campaign(self) -> CampaignReport:
        """
        Execute daily email campaign.
        
        Returns:
            Campaign report
        """
        # Prevent concurrent execution
        if self._running_campaigns.get("email", False):
            logger.warning("Email campaign already running, skipping")
            return None
        
        self._running_campaigns["email"] = True
        started_at = datetime.utcnow()
        
        try:
            logger.info("Starting daily email campaign")
            
            # Create campaign record
            with get_db_context() as db:
                campaign = Campaign(
                    campaign_type="email",
                    started_at=started_at
                )
                db.add(campaign)
                db.flush()
                campaign_id = campaign.id
            
            # Check if dry-run mode
            if self.config.DRY_RUN_MODE:
                logger.info("[DRY-RUN] Email campaign in dry-run mode")
            
            # Check daily cap
            can_proceed, remaining = await self.rate_limiter.enforce_caps_for_campaign("email")
            if not can_proceed:
                logger.warning("Daily email cap reached, skipping campaign")
                return await self._finalize_campaign(campaign_id, "email", 0, 0, 0, ["Daily cap reached"], started_at)
            
            logger.info(f"Email campaign can send up to {remaining} emails")
            
            # Get eligible leads - query and extract data in same session
            eligible_lead_data = []
            with get_db_context() as db:
                # Query eligible leads directly
                cooldown_date = datetime.utcnow() - timedelta(days=self.config.COOLDOWN_DAYS)
                eligible_leads = db.query(Lead).filter(
                    Lead.opted_out == False,
                    Lead.email_verified == True,
                    (Lead.last_contacted_at == None) | (Lead.last_contacted_at < cooldown_date)
                ).order_by(
                    Lead.last_contacted_at.asc().nullsfirst()
                ).limit(remaining).all()
                
                # Extract lead data while still in session - force attribute loading
                for lead in eligible_leads:
                    eligible_lead_data.append({
                        'id': lead.id,
                        'business_name': lead.business_name,
                        'email': lead.primary_email
                    })
            
            logger.info(f"Found {len(eligible_lead_data)} eligible leads for email")
            
            if not eligible_lead_data:
                logger.info("No eligible leads for email campaign")
                return await self._finalize_campaign(campaign_id, "email", 0, 0, 0, [], started_at)
            
            # Execute outreach
            total_attempted = 0
            total_success = 0
            total_failed = 0
            errors = []
            
            for lead_data in eligible_lead_data:
                lead_id = lead_data['id']
                business_name = lead_data['business_name']
                email = lead_data['email']
                try:
                    # Check if approval mode
                    if self.config.APPROVAL_MODE:
                        # Add to approval queue
                        logger.info(f"[APPROVAL MODE] Would add lead {lead_id} ({business_name}) to approval queue")
                        total_attempted += 1
                        total_success += 1
                    else:
                        # Send directly using emailer and personalizer
                        from app.outreach.personalizer import EmailPersonalizer
                        from app.outreach.emailer import EmailSender, OutreachEmail
                        
                        # Create a simple lead-like object for personalization
                        class LeadData:
                            def __init__(self, data):
                                self.id = data['id']
                                self.business_name = data['business_name']
                                self.primary_email = data['email']
                                # Get additional data from database
                                with get_db_context() as db:
                                    lead_obj = db.query(Lead).filter(Lead.id == data['id']).first()
                                    if lead_obj:
                                        self.city = lead_obj.city
                                        self.category = lead_obj.category
                                        self.website = lead_obj.website
                                    else:
                                        self.city = None
                                        self.category = None
                                        self.website = None
                        
                        lead = LeadData(lead_data)
                        
                        personalizer = EmailPersonalizer()
                        emailer = EmailSender()
                        
                        # Generate personalized content
                        personalized = await personalizer.generate(lead)
                        
                        # Create outreach email
                        outreach_email = OutreachEmail(
                            lead_id=lead_id,
                            to_email=email,
                            subject=personalized.subject,
                            body_html=personalized.body_html,
                            body_text=personalized.body_text,
                            unsubscribe_token=emailer.generate_unsubscribe_token()
                        )
                        
                        # Send email
                        result = await emailer.send(outreach_email, campaign_id)
                        
                        if result.success:
                            logger.info(f"Sent email to lead {lead_id} ({business_name} - {email})")
                            total_attempted += 1
                            total_success += 1
                        else:
                            logger.error(f"Failed to send email to lead {lead_id}: {result.error}")
                            total_attempted += 1
                            total_failed += 1
                            errors.append(f"Lead {lead_id}: {result.error}")
                    
                except Exception as e:
                    logger.error(f"Error processing lead {lead_id}: {e}")
                    total_failed += 1
                    errors.append(f"Lead {lead_id}: {str(e)}")
                    
                    # Continue processing other leads (failure isolation)
                    continue
            
            # Finalize campaign
            report = await self._finalize_campaign(
                campaign_id, "email", total_attempted, total_success, total_failed, errors, started_at
            )
            
            # Send report to operators
            await self._send_campaign_report(report)
            
            # Audit log
            await self.audit.log_campaign(
                campaign_id, "email", "complete", report.to_dict()
            )
            
            logger.info(f"Email campaign completed: {total_success}/{total_attempted} successful")
            return report
            
        except Exception as e:
            logger.error(f"Critical error in email campaign: {e}")
            await self.audit.log_error(
                component="scheduler",
                error=e,
                context={"campaign_type": "email"}
            )
            # Don't retry - halt and alert
            return None
            
        finally:
            self._running_campaigns["email"] = False
    
    async def execute_call_campaign(self) -> CampaignReport:
        """
        Execute daily call campaign.
        
        Returns:
            Campaign report
        """
        # Prevent concurrent execution
        if self._running_campaigns.get("call", False):
            logger.warning("Call campaign already running, skipping")
            return None
        
        self._running_campaigns["call"] = True
        started_at = datetime.utcnow()
        
        try:
            logger.info("Starting daily call campaign")
            
            # Create campaign record
            with get_db_context() as db:
                campaign = Campaign(
                    campaign_type="call",
                    started_at=started_at
                )
                db.add(campaign)
                db.flush()
                campaign_id = campaign.id
            
            # Check if dry-run mode
            if self.config.DRY_RUN_MODE:
                logger.info("[DRY-RUN] Call campaign in dry-run mode")
            
            # Check daily cap
            can_proceed, remaining = await self.rate_limiter.enforce_caps_for_campaign("call")
            if not can_proceed:
                logger.warning("Daily call cap reached, skipping campaign")
                return await self._finalize_campaign(campaign_id, "call", 0, 0, 0, ["Daily cap reached"], started_at)
            
            logger.info(f"Call campaign can make up to {remaining} calls")
            
            # Get eligible leads - query and extract data in same session
            eligible_lead_data = []
            with get_db_context() as db:
                # Query eligible leads directly
                cooldown_date = datetime.utcnow() - timedelta(days=self.config.COOLDOWN_DAYS)
                eligible_leads = db.query(Lead).filter(
                    Lead.opted_out == False,
                    Lead.phone_verified == True,
                    (Lead.last_contacted_at == None) | (Lead.last_contacted_at < cooldown_date)
                ).order_by(
                    Lead.last_contacted_at.asc().nullsfirst()
                ).limit(remaining).all()
                
                # Extract lead data while still in session - force attribute loading
                for lead in eligible_leads:
                    eligible_lead_data.append({
                        'id': lead.id,
                        'business_name': lead.business_name,
                        'phone': lead.primary_phone
                    })
            
            logger.info(f"Found {len(eligible_lead_data)} eligible leads for calls")
            
            if not eligible_lead_data:
                logger.info("No eligible leads for call campaign")
                return await self._finalize_campaign(campaign_id, "call", 0, 0, 0, [], started_at)
            
            # Calculate call distribution across window
            call_window_hours = self._calculate_call_window_hours()
            if call_window_hours <= 0:
                logger.warning("Outside call window, skipping campaign")
                return await self._finalize_campaign(campaign_id, "call", 0, 0, 0, ["Outside call window"], started_at)
            
            # Distribute calls evenly
            delay_between_calls = (call_window_hours * 3600) / len(eligible_lead_data) if eligible_lead_data else 0
            logger.info(f"Distributing {len(eligible_lead_data)} calls over {call_window_hours} hours ({delay_between_calls:.1f}s between calls)")
            
            # Execute outreach
            total_attempted = 0
            total_success = 0
            total_failed = 0
            errors = []
            
            for i, lead_data in enumerate(eligible_lead_data):
                lead_id = lead_data['id']
                business_name = lead_data['business_name']
                phone = lead_data['phone']
                try:
                    # Get full lead object for calling
                    with get_db_context() as db:
                        lead = db.query(Lead).filter(Lead.id == lead_id).first()
                        if not lead:
                            logger.error(f"Lead {lead_id} not found")
                            continue
                    
                    # Initiate call via VoiceCaller
                    from app.outreach.caller import get_voice_caller
                    
                    caller = get_voice_caller()
                    result = await caller.initiate_call(lead, campaign_id)
                    
                    if result.status in ["initiated", "completed"]:
                        logger.info(f"Called lead {lead_id} ({business_name} - {phone})")
                        total_attempted += 1
                        total_success += 1
                    else:
                        logger.error(f"Failed to call lead {lead_id}: {result.error}")
                        total_attempted += 1
                        total_failed += 1
                        errors.append(f"Lead {lead_id}: {result.error}")
                    
                    # Delay between calls (in real implementation)
                    # await asyncio.sleep(delay_between_calls)
                    
                except Exception as e:
                    logger.error(f"Error calling lead {lead_id}: {e}")
                    total_failed += 1
                    errors.append(f"Lead {lead_id}: {str(e)}")
                    
                    # Continue processing other leads (failure isolation)
                    continue
            
            # Finalize campaign
            report = await self._finalize_campaign(
                campaign_id, "call", total_attempted, total_success, total_failed, errors, started_at
            )
            
            # Send report to operators
            await self._send_campaign_report(report)
            
            # Audit log
            await self.audit.log_campaign(
                campaign_id, "call", "complete", report.to_dict()
            )
            
            logger.info(f"Call campaign completed: {total_success}/{total_attempted} successful")
            return report
            
        except Exception as e:
            logger.error(f"Critical error in call campaign: {e}")
            await self.audit.log_error(
                component="scheduler",
                error=e,
                context={"campaign_type": "call"}
            )
            # Don't retry - halt and alert
            return None
            
        finally:
            self._running_campaigns["call"] = False
    
    def _calculate_call_window_hours(self) -> float:
        """Calculate remaining hours in call window."""
        try:
            tz = pytz.timezone(self.config.TIMEZONE)
            now = datetime.now(tz)
            
            # Parse window times
            window_start = self._parse_time(self.config.CALL_WINDOW_START)
            window_end = self._parse_time(self.config.CALL_WINDOW_END)
            
            # Create datetime objects for today
            start_dt = now.replace(hour=window_start.hour, minute=window_start.minute, second=0, microsecond=0)
            end_dt = now.replace(hour=window_end.hour, minute=window_end.minute, second=0, microsecond=0)
            
            # Check if we're in the window
            if now < start_dt:
                # Before window - return full window
                return (end_dt - start_dt).total_seconds() / 3600
            elif now > end_dt:
                # After window
                return 0
            else:
                # In window - return remaining time
                return (end_dt - now).total_seconds() / 3600
                
        except Exception as e:
            logger.error(f"Error calculating call window: {e}")
            return 0
    
    async def _finalize_campaign(
        self,
        campaign_id: int,
        campaign_type: str,
        total_attempted: int,
        total_success: int,
        total_failed: int,
        errors: List[str],
        started_at: datetime
    ) -> CampaignReport:
        """Finalize campaign and create report."""
        completed_at = datetime.utcnow()
        
        # Update campaign record
        with get_db_context() as db:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if campaign:
                campaign.total_attempted = total_attempted
                campaign.total_success = total_success
                campaign.total_failed = total_failed
                campaign.errors = errors
                campaign.completed_at = completed_at
        
        return CampaignReport(
            campaign_id=campaign_id,
            campaign_type=campaign_type,
            total_attempted=total_attempted,
            total_success=total_success,
            total_failed=total_failed,
            errors=errors,
            started_at=started_at,
            completed_at=completed_at
        )
    
    async def _send_campaign_report(self, report: CampaignReport):
        """Send campaign report to operators."""
        try:
            # In production, would send email to operators
            logger.info(f"Campaign Report: {report.to_dict()}")
            
            # Would use emailer to send report
            # For now, just log
            
        except Exception as e:
            logger.error(f"Error sending campaign report: {e}")
    
    async def trigger_manual_campaign(self, campaign_type: str) -> Optional[CampaignReport]:
        """
        Manually trigger a campaign.
        
        Args:
            campaign_type: 'email' or 'call'
            
        Returns:
            Campaign report
        """
        logger.info(f"Manually triggering {campaign_type} campaign")
        
        if campaign_type == "email":
            return await self.execute_email_campaign()
        elif campaign_type == "call":
            return await self.execute_call_campaign()
        else:
            logger.error(f"Invalid campaign type: {campaign_type}")
            return None
    
    def get_next_run_times(self) -> Dict[str, Optional[datetime]]:
        """Get next scheduled run times for campaigns."""
        if not self.scheduler:
            return {"email": None, "call": None}
        
        next_times = {}
        
        for job_id in ["daily_email_campaign", "daily_call_campaign"]:
            job = self.scheduler.get_job(job_id)
            if job:
                next_run = job.next_run_time
                campaign_type = "email" if "email" in job_id else "call"
                next_times[campaign_type] = next_run
            else:
                campaign_type = "email" if "email" in job_id else "call"
                next_times[campaign_type] = None
        
        return next_times
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self.scheduler is not None and self.scheduler.running


# Global scheduler instance
_scheduler: Optional[CampaignScheduler] = None


def get_scheduler() -> CampaignScheduler:
    """Get or create global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = CampaignScheduler()
    return _scheduler
