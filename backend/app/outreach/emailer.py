"""Email outreach service with multiple provider support."""

import hashlib
import uuid
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from app.config import get_settings
from app.db import get_db_context
from app.models import OutreachHistory, Lead, OptOut
from app.audit import AuditLogger

logger = logging.getLogger(__name__)


class EmailProvider(str, Enum):
    """Email provider enum."""
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    SMTP = "smtp"


@dataclass
class OutreachEmail:
    """Outreach email data structure."""
    lead_id: int
    to_email: str
    subject: str
    body_html: str
    body_text: str
    unsubscribe_token: str


@dataclass
class SendResult:
    """Email send result."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    provider_response: Dict[str, Any] = None
    sent_at: datetime = None
    
    def __post_init__(self):
        if self.sent_at is None:
            self.sent_at = datetime.utcnow()
        if self.provider_response is None:
            self.provider_response = {}


class EmailSender:
    """Email sender with multiple provider support."""
    
    def __init__(self):
        self.config = get_settings()
        self.audit = AuditLogger()
        self.provider = self._determine_provider()
        self._domain_throttle: Dict[str, List[datetime]] = {}
        
    def _determine_provider(self) -> EmailProvider:
        """Determine which email provider to use based on configuration."""
        if self.config.SENDGRID_API_KEY:
            return EmailProvider.SENDGRID
        elif self.config.MAILGUN_API_KEY:
            return EmailProvider.MAILGUN
        elif self.config.SMTP_HOST:
            return EmailProvider.SMTP
        else:
            raise ValueError("No email provider configured")
    
    def generate_unsubscribe_token(self) -> str:
        """Generate unique unsubscribe token."""
        return str(uuid.uuid4())
    
    def add_compliance_footer(self, body_html: str, body_text: str, unsubscribe_token: str) -> tuple[str, str]:
        """Add compliance footer with unsubscribe link and business address."""
        unsubscribe_url = f"https://devsyncinnovation.com/unsubscribe?token={unsubscribe_token}"
        
        # HTML footer
        html_footer = f"""
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="font-size: 12px; color: #666; margin-top: 20px;">
            <strong>{self.config.EMAIL_FROM_NAME}</strong><br>
            {self.config.BUSINESS_ADDRESS}<br>
            <br>
            You received this email because your business information is publicly listed.
            <a href="{unsubscribe_url}">Unsubscribe</a> from future emails.
        </p>
        """
        
        # Text footer
        text_footer = f"""
        
---
{self.config.EMAIL_FROM_NAME}
{self.config.BUSINESS_ADDRESS}

You received this email because your business information is publicly listed.
Unsubscribe: {unsubscribe_url}
        """
        
        return body_html + html_footer, body_text + text_footer
    
    def calculate_content_hash(self, subject: str, body: str) -> str:
        """Calculate SHA256 hash of email content."""
        content = f"{subject}|{body}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def check_opt_out(self, email: str) -> bool:
        """Check if email is opted out."""
        with get_db_context() as db:
            opt_out = db.query(OptOut).filter(
                OptOut.contact_type == "email",
                OptOut.contact_value == email
            ).first()
            return opt_out is not None
    
    async def check_domain_throttle(self, email: str) -> bool:
        """Check if domain throttle limit is reached."""
        domain = email.split('@')[1] if '@' in email else None
        if not domain:
            return True
        
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        # Clean old entries
        if domain in self._domain_throttle:
            self._domain_throttle[domain] = [
                ts for ts in self._domain_throttle[domain]
                if ts > one_hour_ago
            ]
        else:
            self._domain_throttle[domain] = []
        
        # Check limit
        if len(self._domain_throttle[domain]) >= self.config.PER_DOMAIN_EMAIL_LIMIT:
            logger.warning(f"Domain throttle limit reached for {domain}")
            return False
        
        return True
    
    def record_domain_send(self, email: str):
        """Record email send for domain throttling."""
        domain = email.split('@')[1] if '@' in email else None
        if domain:
            if domain not in self._domain_throttle:
                self._domain_throttle[domain] = []
            self._domain_throttle[domain].append(datetime.utcnow())
    
    async def persist_before_send(self, email: OutreachEmail, content_hash: str, campaign_id: Optional[int] = None) -> int:
        """Persist email content to database before sending."""
        with get_db_context() as db:
            history = OutreachHistory(
                lead_id=email.lead_id,
                campaign_id=campaign_id,
                outreach_type="email",
                content_hash=content_hash,
                status="pending",
                provider_response={"to": email.to_email, "subject": email.subject},
                attempted_at=datetime.utcnow()
            )
            db.add(history)
            db.flush()
            return history.id
    
    async def update_send_result(self, history_id: int, result: SendResult):
        """Update outreach history with send result."""
        with get_db_context() as db:
            history = db.query(OutreachHistory).filter(OutreachHistory.id == history_id).first()
            if history:
                history.status = "sent" if result.success else "failed"
                history.provider_message_id = result.message_id
                history.provider_response = result.provider_response
                history.completed_at = result.sent_at
    
    async def send(self, email: OutreachEmail, campaign_id: Optional[int] = None) -> SendResult:
        """Send email through configured provider with all checks and retries."""
        # Check if dry-run mode
        if self.config.DRY_RUN_MODE:
            logger.info(f"[DRY-RUN] Would send email to {email.to_email}: {email.subject}")
            await self.audit.log_outreach(
                email.lead_id,
                "email",
                {"status": "dry-run", "to": email.to_email, "subject": email.subject}
            )
            return SendResult(
                success=True,
                message_id=f"dry-run-{uuid.uuid4()}",
                provider_response={"mode": "dry-run"}
            )
        
        # Check opt-out status
        if await self.check_opt_out(email.to_email):
            logger.warning(f"Email {email.to_email} is opted out, skipping")
            return SendResult(
                success=False,
                error="Email is opted out"
            )
        
        # Check domain throttle
        if not await self.check_domain_throttle(email.to_email):
            return SendResult(
                success=False,
                error="Domain throttle limit reached"
            )
        
        # Add compliance footer
        body_html, body_text = self.add_compliance_footer(
            email.body_html,
            email.body_text,
            email.unsubscribe_token
        )
        
        # Calculate content hash
        content_hash = self.calculate_content_hash(email.subject, body_text)
        
        # Persist before sending
        history_id = await self.persist_before_send(email, content_hash, campaign_id)
        
        # Send with retries
        result = await self._send_with_retry(email, body_html, body_text)
        
        # Update history
        await self.update_send_result(history_id, result)
        
        # Record domain send if successful
        if result.success:
            self.record_domain_send(email.to_email)
        
        # Audit log
        await self.audit.log_outreach(
            email.lead_id,
            "email",
            {
                "status": "sent" if result.success else "failed",
                "to": email.to_email,
                "subject": email.subject,
                "message_id": result.message_id,
                "error": result.error
            }
        )
        
        return result
    
    async def _send_with_retry(self, email: OutreachEmail, body_html: str, body_text: str, max_retries: int = 3) -> SendResult:
        """Send email with exponential backoff retry logic."""
        for attempt in range(max_retries):
            try:
                if self.provider == EmailProvider.SENDGRID:
                    result = await self._send_via_sendgrid(email, body_html, body_text)
                elif self.provider == EmailProvider.MAILGUN:
                    result = await self._send_via_mailgun(email, body_html, body_text)
                elif self.provider == EmailProvider.SMTP:
                    result = await self._send_via_smtp(email, body_html, body_text)
                else:
                    return SendResult(success=False, error="Unknown provider")
                
                if result.success:
                    return result
                
                # Check if error is permanent
                if self._is_permanent_error(result.error):
                    logger.error(f"Permanent error sending email: {result.error}")
                    return result
                
                # Retry on transient error
                if attempt < max_retries - 1:
                    delay = self._calculate_backoff(attempt)
                    logger.warning(f"Transient error, retrying in {delay}s: {result.error}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Exhausted retries sending email: {result.error}")
                    return result
                    
            except Exception as e:
                logger.error(f"Exception sending email (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    delay = self._calculate_backoff(attempt)
                    await asyncio.sleep(delay)
                else:
                    return SendResult(success=False, error=str(e))
        
        return SendResult(success=False, error="Max retries exceeded")
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        base_delay = 1.0
        max_delay = 16.0
        delay = min(base_delay * (4 ** attempt), max_delay)
        return delay
    
    def _is_permanent_error(self, error: Optional[str]) -> bool:
        """Check if error is permanent (no retry needed)."""
        if not error:
            return False
        
        permanent_indicators = [
            "invalid recipient",
            "invalid email",
            "blocked",
            "blacklisted",
            "unsubscribed",
            "does not exist",
            "401",
            "403",
            "404"
        ]
        
        error_lower = error.lower()
        return any(indicator in error_lower for indicator in permanent_indicators)
    
    async def _send_via_sendgrid(self, email: OutreachEmail, body_html: str, body_text: str) -> SendResult:
        """Send email via SendGrid API."""
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {self.config.SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "personalizations": [{
                "to": [{"email": email.to_email}],
                "subject": email.subject
            }],
            "from": {
                "email": self.config.EMAIL_FROM,
                "name": self.config.EMAIL_FROM_NAME
            },
            "content": [
                {"type": "text/plain", "value": body_text},
                {"type": "text/html", "value": body_html}
            ],
            "headers": {
                "List-Unsubscribe": f"<https://devsyncinnovation.com/unsubscribe?token={email.unsubscribe_token}>",
                "Precedence": "bulk"
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code == 202:
                message_id = response.headers.get("X-Message-Id", str(uuid.uuid4()))
                return SendResult(
                    success=True,
                    message_id=message_id,
                    provider_response={"status_code": response.status_code}
                )
            else:
                return SendResult(
                    success=False,
                    error=f"SendGrid error: {response.status_code} - {response.text}",
                    provider_response={"status_code": response.status_code, "body": response.text}
                )
    
    async def _send_via_mailgun(self, email: OutreachEmail, body_html: str, body_text: str) -> SendResult:
        """Send email via Mailgun API."""
        url = f"https://api.mailgun.net/v3/{self.config.MAILGUN_DOMAIN}/messages"
        auth = ("api", self.config.MAILGUN_API_KEY)
        
        data = {
            "from": f"{self.config.EMAIL_FROM_NAME} <{self.config.EMAIL_FROM}>",
            "to": email.to_email,
            "subject": email.subject,
            "text": body_text,
            "html": body_html,
            "h:List-Unsubscribe": f"<https://devsyncinnovation.com/unsubscribe?token={email.unsubscribe_token}>",
            "h:Precedence": "bulk"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data, auth=auth)
            
            if response.status_code == 200:
                response_data = response.json()
                message_id = response_data.get("id", str(uuid.uuid4()))
                return SendResult(
                    success=True,
                    message_id=message_id,
                    provider_response=response_data
                )
            else:
                return SendResult(
                    success=False,
                    error=f"Mailgun error: {response.status_code} - {response.text}",
                    provider_response={"status_code": response.status_code, "body": response.text}
                )
    
    async def _send_via_smtp(self, email: OutreachEmail, body_html: str, body_text: str) -> SendResult:
        """Send email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = email.subject
            msg['From'] = f"{self.config.EMAIL_FROM_NAME} <{self.config.EMAIL_FROM}>"
            msg['To'] = email.to_email
            msg['List-Unsubscribe'] = f"<https://devsyncinnovation.com/unsubscribe?token={email.unsubscribe_token}>"
            msg['Precedence'] = 'bulk'
            
            # Attach parts
            part1 = MIMEText(body_text, 'plain')
            part2 = MIMEText(body_html, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send via SMTP
            with smtplib.SMTP(self.config.SMTP_HOST, self.config.SMTP_PORT) as server:
                server.starttls()
                server.login(self.config.SMTP_USER, self.config.SMTP_PASSWORD)
                server.send_message(msg)
            
            return SendResult(
                success=True,
                message_id=str(uuid.uuid4()),
                provider_response={"method": "smtp"}
            )
            
        except Exception as e:
            return SendResult(
                success=False,
                error=f"SMTP error: {str(e)}",
                provider_response={"error": str(e)}
            )
    
    async def handle_webhook(self, event: Dict[str, Any]) -> None:
        """Process webhook events from email provider."""
        event_type = event.get("event", event.get("type", "unknown"))
        
        logger.info(f"Processing webhook event: {event_type}")
        
        # Extract email and message ID
        email_address = event.get("email", event.get("recipient"))
        message_id = event.get("message_id", event.get("sg_message_id"))
        
        if not email_address:
            logger.warning("Webhook event missing email address")
            return
        
        # Handle different event types
        if event_type in ["bounce", "dropped", "bounced"]:
            await self._handle_bounce(email_address, message_id, event)
        elif event_type in ["complaint", "spamreport"]:
            await self._handle_complaint(email_address, message_id, event)
        elif event_type in ["unsubscribe", "unsubscribed"]:
            await self._handle_unsubscribe(email_address, "webhook", event)
        elif event_type in ["delivered", "delivery"]:
            await self._handle_delivered(email_address, message_id, event)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
    
    async def _handle_bounce(self, email: str, message_id: Optional[str], event: Dict[str, Any]):
        """Handle bounce event."""
        logger.warning(f"Email bounced: {email}")
        
        # Update lead as undeliverable
        with get_db_context() as db:
            lead = db.query(Lead).filter(Lead.primary_email == email).first()
            if lead:
                lead.email_verified = False
                logger.info(f"Marked lead {lead.id} email as unverified due to bounce")
            
            # Update outreach history
            if message_id:
                history = db.query(OutreachHistory).filter(
                    OutreachHistory.provider_message_id == message_id
                ).first()
                if history:
                    history.status = "bounced"
                    history.provider_response = event
        
        await self.audit.log_api_call("email_webhook", "bounce", {"email": email, "event": event})
    
    async def _handle_complaint(self, email: str, message_id: Optional[str], event: Dict[str, Any]):
        """Handle spam complaint event."""
        logger.warning(f"Spam complaint received: {email}")
        
        # Automatically opt out
        await self._handle_unsubscribe(email, "complaint", event)
        
        await self.audit.log_api_call("email_webhook", "complaint", {"email": email, "event": event})
    
    async def _handle_unsubscribe(self, email: str, method: str, event: Dict[str, Any]):
        """Handle unsubscribe event."""
        logger.info(f"Unsubscribe request: {email} via {method}")
        
        with get_db_context() as db:
            # Check if already opted out
            existing = db.query(OptOut).filter(
                OptOut.contact_type == "email",
                OptOut.contact_value == email
            ).first()
            
            if not existing:
                # Create opt-out record
                opt_out = OptOut(
                    contact_type="email",
                    contact_value=email,
                    opt_out_method=method,
                    opted_out_at=datetime.utcnow()
                )
                db.add(opt_out)
                
                # Update lead
                lead = db.query(Lead).filter(Lead.primary_email == email).first()
                if lead:
                    lead.opted_out = True
                    lead.opted_out_at = datetime.utcnow()
                    lead.opted_out_method = method
                    opt_out.source_lead_id = lead.id
                
                logger.info(f"Created opt-out record for {email}")
        
        await self.audit.log_opt_out(email, method)
    
    async def _handle_delivered(self, email: str, message_id: Optional[str], event: Dict[str, Any]):
        """Handle delivery confirmation event."""
        logger.info(f"Email delivered: {email}")
        
        if message_id:
            with get_db_context() as db:
                history = db.query(OutreachHistory).filter(
                    OutreachHistory.provider_message_id == message_id
                ).first()
                if history:
                    history.status = "delivered"
                    history.provider_response = event

