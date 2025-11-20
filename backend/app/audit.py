"""Audit logging system with structured logging and sensitive data masking."""

import logging
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from app.models import AuditLog
from app.db import get_db_context
from app.config import get_settings

logger = logging.getLogger(__name__)


class AuditLogger:
    """Comprehensive audit logging system."""
    
    # Sensitive field patterns to mask
    SENSITIVE_PATTERNS = [
        r'api[_-]?key',
        r'auth[_-]?token',
        r'password',
        r'secret',
        r'credential',
        r'private[_-]?key',
        r'access[_-]?token',
    ]
    
    # Email/phone patterns to partially mask
    EMAIL_PATTERN = re.compile(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})')
    PHONE_PATTERN = re.compile(r'\+?(\d{1,3})?[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})')
    
    def __init__(self):
        """Initialize audit logger."""
        self.settings = get_settings()
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up structured logging."""
        log_level = getattr(logging, self.settings.LOG_LEVEL.upper(), logging.INFO)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
    
    def _mask_sensitive_data(self, data: Any) -> Any:
        """Recursively mask sensitive data in dictionaries, lists, and strings."""
        if isinstance(data, dict):
            return {
                key: self._mask_value(key, value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        elif isinstance(data, str):
            return self._mask_string(data)
        else:
            return data
    
    def _mask_value(self, key: str, value: Any) -> Any:
        """Mask value if key matches sensitive pattern."""
        key_lower = key.lower()
        
        # Check if key matches sensitive patterns
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, key_lower):
                if isinstance(value, str) and len(value) > 8:
                    return f"{value[:4]}...{value[-4:]}"
                else:
                    return "****"
        
        # Recursively mask nested structures
        return self._mask_sensitive_data(value)
    
    def _mask_string(self, text: str) -> str:
        """Mask emails and phone numbers in strings."""
        # Mask emails: show first 2 chars and domain
        text = self.EMAIL_PATTERN.sub(
            lambda m: f"{m.group(1)[:2]}***@{m.group(2)}",
            text
        )
        
        # Mask phone numbers: show country code and last 4 digits
        text = self.PHONE_PATTERN.sub(
            lambda m: f"+{m.group(1) or '**'}***{m.group(4)}",
            text
        )
        
        return text
    
    def _format_log_entry(
        self,
        log_level: str,
        component: str,
        action: str,
        details: Dict[str, Any],
        lead_id: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format log entry as structured JSON."""
        masked_details = self._mask_sensitive_data(details)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "log_level": log_level,
            "component": component,
            "action": action,
            "lead_id": lead_id,
            "user_id": user_id,
            "details": masked_details
        }
    
    async def log_outreach(
        self,
        lead_id: int,
        outreach_type: str,
        result: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> None:
        """
        Log outreach attempt (email or call).
        
        Args:
            lead_id: ID of the lead contacted
            outreach_type: 'email' or 'call'
            result: Result dictionary with status, provider response, etc.
            user_id: Optional user who initiated the outreach
        """
        log_entry = self._format_log_entry(
            log_level="INFO",
            component="outreach",
            action=f"send_{outreach_type}",
            details=result,
            lead_id=lead_id,
            user_id=user_id
        )
        
        # Log to stdout
        logger.info(json.dumps(log_entry))
        
        # Store in database
        try:
            with get_db_context() as db:
                audit_log = AuditLog(
                    log_level="INFO",
                    component="outreach",
                    action=f"send_{outreach_type}",
                    lead_id=lead_id,
                    user_id=user_id,
                    details=self._mask_sensitive_data(result)
                )
                db.add(audit_log)
        except Exception as e:
            logger.error(f"Failed to store audit log in database: {e}")
    
    async def log_opt_out(
        self,
        contact: str,
        method: str,
        lead_id: Optional[int] = None
    ) -> None:
        """
        Log opt-out request.
        
        Args:
            contact: Email or phone that opted out
            method: How they opted out (link, email_reply, call_request, sms)
            lead_id: Optional lead ID if known
        """
        log_entry = self._format_log_entry(
            log_level="WARNING",
            component="opt_out",
            action="opt_out_request",
            details={
                "contact": contact,
                "method": method,
                "timestamp": datetime.utcnow().isoformat()
            },
            lead_id=lead_id
        )
        
        logger.warning(json.dumps(log_entry))
        
        try:
            with get_db_context() as db:
                audit_log = AuditLog(
                    log_level="WARNING",
                    component="opt_out",
                    action="opt_out_request",
                    lead_id=lead_id,
                    details=self._mask_sensitive_data({
                        "contact": contact,
                        "method": method
                    })
                )
                db.add(audit_log)
        except Exception as e:
            logger.error(f"Failed to store opt-out audit log: {e}")
    
    async def log_api_call(
        self,
        service: str,
        endpoint: str,
        result: Dict[str, Any],
        lead_id: Optional[int] = None
    ) -> None:
        """
        Log external API call.
        
        Args:
            service: Service name (e.g., 'sendgrid', 'twilio', 'openai')
            endpoint: API endpoint called
            result: Result dictionary with status, response, etc.
            lead_id: Optional lead ID if related to a lead
        """
        log_entry = self._format_log_entry(
            log_level="DEBUG",
            component="api",
            action=f"{service}_{endpoint}",
            details=result,
            lead_id=lead_id
        )
        
        logger.debug(json.dumps(log_entry))
        
        # Only store API logs if debug level
        if self.settings.LOG_LEVEL == "DEBUG":
            try:
                with get_db_context() as db:
                    audit_log = AuditLog(
                        log_level="DEBUG",
                        component="api",
                        action=f"{service}_{endpoint}",
                        lead_id=lead_id,
                        details=self._mask_sensitive_data(result)
                    )
                    db.add(audit_log)
            except Exception as e:
                logger.error(f"Failed to store API audit log: {e}")
    
    async def log_error(
        self,
        component: str,
        error: Exception,
        context: Dict[str, Any],
        lead_id: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Log error with context.
        
        Args:
            component: Component where error occurred
            error: The exception that was raised
            context: Additional context about the error
            lead_id: Optional lead ID if related
            user_id: Optional user ID if related
        """
        error_details = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context
        }
        
        log_entry = self._format_log_entry(
            log_level="ERROR",
            component=component,
            action="error",
            details=error_details,
            lead_id=lead_id,
            user_id=user_id
        )
        
        logger.error(json.dumps(log_entry), exc_info=True)
        
        try:
            with get_db_context() as db:
                audit_log = AuditLog(
                    log_level="ERROR",
                    component=component,
                    action="error",
                    lead_id=lead_id,
                    user_id=user_id,
                    details=self._mask_sensitive_data(error_details)
                )
                db.add(audit_log)
        except Exception as e:
            logger.error(f"Failed to store error audit log: {e}")
    
    async def log_verification(
        self,
        lead_id: int,
        verification_type: str,
        result: Dict[str, Any]
    ) -> None:
        """
        Log verification attempt.
        
        Args:
            lead_id: ID of the lead being verified
            verification_type: 'email' or 'phone'
            result: Verification result
        """
        log_entry = self._format_log_entry(
            log_level="INFO",
            component="verification",
            action=f"verify_{verification_type}",
            details=result,
            lead_id=lead_id
        )
        
        logger.info(json.dumps(log_entry))
        
        try:
            with get_db_context() as db:
                audit_log = AuditLog(
                    log_level="INFO",
                    component="verification",
                    action=f"verify_{verification_type}",
                    lead_id=lead_id,
                    details=self._mask_sensitive_data(result)
                )
                db.add(audit_log)
        except Exception as e:
            logger.error(f"Failed to store verification audit log: {e}")
    
    async def log_campaign(
        self,
        campaign_id: int,
        campaign_type: str,
        action: str,
        details: Dict[str, Any]
    ) -> None:
        """
        Log campaign event.
        
        Args:
            campaign_id: Campaign ID
            campaign_type: 'email' or 'call'
            action: Action taken (start, complete, error)
            details: Campaign details
        """
        log_entry = self._format_log_entry(
            log_level="INFO",
            component="campaign",
            action=f"{campaign_type}_{action}",
            details={**details, "campaign_id": campaign_id}
        )
        
        logger.info(json.dumps(log_entry))
        
        try:
            with get_db_context() as db:
                audit_log = AuditLog(
                    log_level="INFO",
                    component="campaign",
                    action=f"{campaign_type}_{action}",
                    details=self._mask_sensitive_data({**details, "campaign_id": campaign_id})
                )
                db.add(audit_log)
        except Exception as e:
            logger.error(f"Failed to store campaign audit log: {e}")
    
    async def log_approval(
        self,
        approval_id: int,
        action: str,
        user_id: str,
        lead_id: Optional[int] = None
    ) -> None:
        """
        Log approval queue action.
        
        Args:
            approval_id: Approval queue item ID
            action: Action taken (approve, reject, edit)
            user_id: User who performed the action
            lead_id: Optional lead ID
        """
        log_entry = self._format_log_entry(
            log_level="INFO",
            component="approval",
            action=action,
            details={"approval_id": approval_id},
            lead_id=lead_id,
            user_id=user_id
        )
        
        logger.info(json.dumps(log_entry))
        
        try:
            with get_db_context() as db:
                audit_log = AuditLog(
                    log_level="INFO",
                    component="approval",
                    action=action,
                    lead_id=lead_id,
                    user_id=user_id,
                    details={"approval_id": approval_id}
                )
                db.add(audit_log)
        except Exception as e:
            logger.error(f"Failed to store approval audit log: {e}")
    
    async def purge_old_logs(self, retention_days: Optional[int] = None) -> int:
        """
        Purge logs older than retention period.
        
        Args:
            retention_days: Days to retain logs (uses config default if not provided)
            
        Returns:
            Number of logs deleted
        """
        if retention_days is None:
            retention_days = self.settings.LOG_RETENTION_DAYS
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        try:
            with get_db_context() as db:
                # Delete old logs except opt-out logs (those are permanent)
                deleted = db.query(AuditLog).filter(
                    AuditLog.created_at < cutoff_date,
                    AuditLog.component != "opt_out"
                ).delete()
                
                logger.info(f"Purged {deleted} audit logs older than {retention_days} days")
                return deleted
        except Exception as e:
            logger.error(f"Failed to purge old audit logs: {e}")
            return 0
    
    async def get_logs(
        self,
        component: Optional[str] = None,
        action: Optional[str] = None,
        lead_id: Optional[int] = None,
        log_level: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Query audit logs with filters.
        
        Args:
            component: Filter by component
            action: Filter by action
            lead_id: Filter by lead ID
            log_level: Filter by log level
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of logs to return
            
        Returns:
            List of audit logs
        """
        try:
            with get_db_context() as db:
                query = db.query(AuditLog)
                
                if component:
                    query = query.filter(AuditLog.component == component)
                if action:
                    query = query.filter(AuditLog.action == action)
                if lead_id:
                    query = query.filter(AuditLog.lead_id == lead_id)
                if log_level:
                    query = query.filter(AuditLog.log_level == log_level)
                if start_date:
                    query = query.filter(AuditLog.created_at >= start_date)
                if end_date:
                    query = query.filter(AuditLog.created_at <= end_date)
                
                logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
                return logs
        except Exception as e:
            logger.error(f"Failed to query audit logs: {e}")
            return []


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


@contextmanager
def audit_context(component: str, action: str, lead_id: Optional[int] = None):
    """
    Context manager for auditing operations.
    
    Usage:
        with audit_context("emailer", "send_email", lead_id=123):
            # Perform operation
            send_email(...)
    """
    audit = get_audit_logger()
    start_time = datetime.utcnow()
    
    try:
        yield audit
        # Log success
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"{component}.{action} completed in {duration:.2f}s")
    except Exception as e:
        # Log error
        duration = (datetime.utcnow() - start_time).total_seconds()
        import asyncio
        asyncio.create_task(audit.log_error(
            component=component,
            error=e,
            context={"action": action, "duration": duration},
            lead_id=lead_id
        ))
        raise
