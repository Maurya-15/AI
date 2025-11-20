"""Rate limiting and caps enforcement."""

import logging
from typing import Optional, Dict
from datetime import datetime, timedelta, date
from collections import defaultdict

from app.db import get_db_context
from app.models import OutreachHistory, Lead
from app.config import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Enforce rate limits and daily caps for outreach."""
    
    def __init__(self):
        """Initialize rate limiter."""
        self.config = get_settings()
        # In-memory tracking (would use Redis in production)
        self._daily_counts: Dict[str, Dict[date, int]] = defaultdict(lambda: defaultdict(int))
        self._domain_counts: Dict[str, Dict[datetime, int]] = defaultdict(lambda: defaultdict(int))
    
    async def check_daily_email_cap(self) -> tuple[bool, int, int]:
        """
        Check if daily email cap has been reached.
        
        Returns:
            Tuple of (can_send, sent_today, remaining)
        """
        try:
            today = date.today()
            cap = self.config.DAILY_EMAIL_CAP
            
            # Count emails sent today from database
            with get_db_context() as db:
                sent_today = db.query(OutreachHistory).filter(
                    OutreachHistory.outreach_type == "email",
                    OutreachHistory.attempted_at >= datetime.combine(today, datetime.min.time())
                ).count()
            
            remaining = max(0, cap - sent_today)
            can_send = sent_today < cap
            
            return can_send, sent_today, remaining
            
        except Exception as e:
            logger.error(f"Error checking daily email cap: {e}")
            return False, 0, 0
    
    async def check_daily_call_cap(self) -> tuple[bool, int, int]:
        """
        Check if daily call cap has been reached.
        
        Returns:
            Tuple of (can_send, sent_today, remaining)
        """
        try:
            today = date.today()
            cap = self.config.DAILY_CALL_CAP
            
            # Count calls made today from database
            with get_db_context() as db:
                calls_today = db.query(OutreachHistory).filter(
                    OutreachHistory.outreach_type == "call",
                    OutreachHistory.attempted_at >= datetime.combine(today, datetime.min.time())
                ).count()
            
            remaining = max(0, cap - calls_today)
            can_send = calls_today < cap
            
            return can_send, calls_today, remaining
            
        except Exception as e:
            logger.error(f"Error checking daily call cap: {e}")
            return False, 0, 0
    
    async def increment_daily_email_count(self) -> int:
        """
        Increment daily email count.
        
        Returns:
            New count for today
        """
        today = date.today()
        self._daily_counts["email"][today] += 1
        return self._daily_counts["email"][today]
    
    async def increment_daily_call_count(self) -> int:
        """
        Increment daily call count.
        
        Returns:
            New count for today
        """
        today = date.today()
        self._daily_counts["call"][today] += 1
        return self._daily_counts["call"][today]
    
    async def check_domain_throttle(self, email: str) -> tuple[bool, int]:
        """
        Check if domain throttle limit has been reached.
        
        Args:
            email: Email address to check
            
        Returns:
            Tuple of (can_send, count_in_last_hour)
        """
        try:
            domain = email.split('@')[1] if '@' in email else None
            if not domain:
                return True, 0
            
            now = datetime.utcnow()
            one_hour_ago = now - timedelta(hours=1)
            
            # Count emails to this domain in last hour
            with get_db_context() as db:
                # Get all outreach history for emails
                recent_emails = db.query(OutreachHistory).filter(
                    OutreachHistory.outreach_type == "email",
                    OutreachHistory.attempted_at >= one_hour_ago
                ).all()
                
                # Count emails to this domain
                domain_count = 0
                for history in recent_emails:
                    # Get lead email
                    lead = db.query(Lead).filter(Lead.id == history.lead_id).first()
                    if lead and lead.primary_email:
                        lead_domain = lead.primary_email.split('@')[1] if '@' in lead.primary_email else None
                        if lead_domain == domain:
                            domain_count += 1
            
            limit = self.config.PER_DOMAIN_EMAIL_LIMIT
            can_send = domain_count < limit
            
            return can_send, domain_count
            
        except Exception as e:
            logger.error(f"Error checking domain throttle: {e}")
            return True, 0  # Allow on error to avoid blocking
    
    async def check_cooldown(self, lead_id: int) -> tuple[bool, Optional[datetime]]:
        """
        Check if lead is in cooldown period.
        
        Args:
            lead_id: Lead ID to check
            
        Returns:
            Tuple of (can_contact, last_contacted_at)
        """
        try:
            with get_db_context() as db:
                lead = db.query(Lead).filter(Lead.id == lead_id).first()
                
                if not lead:
                    return False, None
                
                if not lead.last_contacted_at:
                    return True, None
                
                cooldown_days = self.config.COOLDOWN_DAYS
                cooldown_end = lead.last_contacted_at + timedelta(days=cooldown_days)
                now = datetime.utcnow()
                
                can_contact = now >= cooldown_end
                
                return can_contact, lead.last_contacted_at
                
        except Exception as e:
            logger.error(f"Error checking cooldown for lead {lead_id}: {e}")
            return False, None
    
    async def get_leads_eligible_for_outreach(
        self,
        outreach_type: str,
        limit: Optional[int] = None
    ) -> list:
        """
        Get leads eligible for outreach (verified, not opted out, not in cooldown).
        
        Args:
            outreach_type: 'email' or 'call'
            limit: Maximum number of leads to return
            
        Returns:
            List of eligible leads
        """
        try:
            with get_db_context() as db:
                # Base query: verified and not opted out
                query = db.query(Lead).filter(
                    Lead.opted_out == False
                )
                
                # Type-specific verification
                if outreach_type == "email":
                    query = query.filter(Lead.email_verified == True)
                elif outreach_type == "call":
                    query = query.filter(Lead.phone_verified == True)
                
                # Cooldown filter
                cooldown_date = datetime.utcnow() - timedelta(days=self.config.COOLDOWN_DAYS)
                query = query.filter(
                    (Lead.last_contacted_at == None) | 
                    (Lead.last_contacted_at < cooldown_date)
                )
                
                # Order by never contacted first, then oldest contact
                query = query.order_by(
                    Lead.last_contacted_at.asc().nullsfirst()
                )
                
                if limit:
                    query = query.limit(limit)
                
                leads = query.all()
                return leads
                
        except Exception as e:
            logger.error(f"Error getting eligible leads: {e}")
            return []
    
    async def enforce_caps_for_campaign(
        self,
        outreach_type: str
    ) -> tuple[bool, int]:
        """
        Check if campaign can proceed based on daily caps.
        
        Args:
            outreach_type: 'email' or 'call'
            
        Returns:
            Tuple of (can_proceed, remaining_capacity)
        """
        if outreach_type == "email":
            can_send, sent, remaining = await self.check_daily_email_cap()
            return can_send, remaining
        elif outreach_type == "call":
            can_send, sent, remaining = await self.check_daily_call_cap()
            return can_send, remaining
        else:
            return False, 0
    
    async def get_rate_limit_status(self) -> Dict[str, any]:
        """
        Get current rate limit status.
        
        Returns:
            Dictionary with rate limit information
        """
        email_can_send, email_sent, email_remaining = await self.check_daily_email_cap()
        call_can_send, call_sent, call_remaining = await self.check_daily_call_cap()
        
        return {
            "email": {
                "cap": self.config.DAILY_EMAIL_CAP,
                "sent_today": email_sent,
                "remaining": email_remaining,
                "can_send": email_can_send
            },
            "call": {
                "cap": self.config.DAILY_CALL_CAP,
                "sent_today": call_sent,
                "remaining": call_remaining,
                "can_send": call_can_send
            },
            "cooldown_days": self.config.COOLDOWN_DAYS,
            "per_domain_limit": self.config.PER_DOMAIN_EMAIL_LIMIT
        }
    
    async def reset_daily_counts(self):
        """Reset daily counts (for testing or manual reset)."""
        self._daily_counts.clear()
        logger.info("Reset daily counts")
    
    def _clean_old_domain_counts(self):
        """Clean up old domain count entries."""
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        for domain in list(self._domain_counts.keys()):
            # Remove old timestamps
            old_timestamps = [
                ts for ts in self._domain_counts[domain].keys()
                if ts < one_hour_ago
            ]
            for ts in old_timestamps:
                del self._domain_counts[domain][ts]
            
            # Remove domain if no recent activity
            if not self._domain_counts[domain]:
                del self._domain_counts[domain]


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
