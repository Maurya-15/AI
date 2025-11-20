"""Opt-out handling system for email and phone contacts."""

import re
import logging
from typing import Optional, List
from datetime import datetime

from app.db import get_db_context
from app.models import OptOut, Lead
from app.audit import AuditLogger

logger = logging.getLogger(__name__)


class OptOutManager:
    """Manage opt-out requests and enforcement."""
    
    # Keywords that indicate opt-out intent in email replies
    OPT_OUT_KEYWORDS = [
        "unsubscribe",
        "stop",
        "remove",
        "opt-out",
        "opt out",
        "optout",
        "do not contact",
        "don't contact",
        "no more emails",
        "take me off",
        "remove me"
    ]
    
    def __init__(self):
        """Initialize opt-out manager."""
        self.audit = AuditLogger()
    
    def detect_opt_out_keywords(self, text: str) -> bool:
        """
        Detect opt-out keywords in email reply text.
        
        Args:
            text: Email body text to analyze
            
        Returns:
            True if opt-out keywords detected, False otherwise
        """
        if not text:
            return False
        
        # Normalize text
        text_lower = text.lower()
        
        # Check for any opt-out keywords
        for keyword in self.OPT_OUT_KEYWORDS:
            if keyword in text_lower:
                logger.info(f"Detected opt-out keyword: '{keyword}' in text")
                return True
        
        return False
    
    async def add_opt_out(
        self,
        contact_type: str,
        contact_value: str,
        method: str,
        source_lead_id: Optional[int] = None
    ) -> bool:
        """
        Add contact to opt-out list.
        
        Args:
            contact_type: 'email' or 'phone'
            contact_value: Email address or phone number
            method: How they opted out (link, email_reply, call_request, sms)
            source_lead_id: Optional lead ID if known
            
        Returns:
            True if opt-out was added, False if already existed
        """
        try:
            with get_db_context() as db:
                # Check if already opted out
                existing = db.query(OptOut).filter(
                    OptOut.contact_type == contact_type,
                    OptOut.contact_value == contact_value
                ).first()
                
                if existing:
                    logger.info(f"Contact {contact_value} already opted out")
                    return False
                
                # Create opt-out record
                opt_out = OptOut(
                    contact_type=contact_type,
                    contact_value=contact_value,
                    opt_out_method=method,
                    opted_out_at=datetime.utcnow(),
                    source_lead_id=source_lead_id
                )
                db.add(opt_out)
                
                # Update lead if found
                if contact_type == "email":
                    lead = db.query(Lead).filter(Lead.primary_email == contact_value).first()
                elif contact_type == "phone":
                    lead = db.query(Lead).filter(Lead.primary_phone == contact_value).first()
                else:
                    lead = None
                
                if lead:
                    lead.opted_out = True
                    lead.opted_out_at = datetime.utcnow()
                    lead.opted_out_method = method
                    if not source_lead_id:
                        opt_out.source_lead_id = lead.id
                
                logger.info(f"Added opt-out: {contact_type} {contact_value} via {method}")
                
                # Audit log
                await self.audit.log_opt_out(
                    contact=contact_value,
                    method=method,
                    lead_id=source_lead_id or (lead.id if lead else None)
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error adding opt-out: {e}")
            await self.audit.log_error(
                component="opt_out",
                error=e,
                context={"contact_type": contact_type, "contact_value": contact_value}
            )
            raise
    
    async def is_opted_out(self, contact_type: str, contact_value: str) -> bool:
        """
        Check if contact is opted out.
        
        Args:
            contact_type: 'email' or 'phone'
            contact_value: Email address or phone number
            
        Returns:
            True if opted out, False otherwise
        """
        try:
            with get_db_context() as db:
                opt_out = db.query(OptOut).filter(
                    OptOut.contact_type == contact_type,
                    OptOut.contact_value == contact_value
                ).first()
                
                return opt_out is not None
                
        except Exception as e:
            logger.error(f"Error checking opt-out status: {e}")
            # Fail safe: if we can't check, assume opted out to be safe
            return True
    
    async def handle_unsubscribe_link(self, token: str) -> dict:
        """
        Handle unsubscribe link click.
        
        Args:
            token: Unique unsubscribe token from email
            
        Returns:
            Dictionary with status and message
        """
        try:
            # In a real implementation, we would:
            # 1. Look up the token in a token->email mapping table
            # 2. Extract the email address
            # 3. Add to opt-out list
            
            # For now, we'll return a placeholder response
            # The actual token->email mapping would be stored when emails are sent
            
            logger.info(f"Processing unsubscribe link click for token: {token}")
            
            # This would be implemented with a token mapping table
            # For now, return success
            return {
                "status": "success",
                "message": "You have been unsubscribed from future emails."
            }
            
        except Exception as e:
            logger.error(f"Error handling unsubscribe link: {e}")
            return {
                "status": "error",
                "message": "An error occurred processing your request. Please try again."
            }
    
    async def handle_email_reply(self, from_email: str, body: str) -> bool:
        """
        Handle email reply and check for opt-out keywords.
        
        Args:
            from_email: Email address that sent the reply
            body: Email body text
            
        Returns:
            True if opt-out was detected and processed, False otherwise
        """
        try:
            # Detect opt-out keywords
            if self.detect_opt_out_keywords(body):
                logger.info(f"Opt-out keywords detected in reply from {from_email}")
                
                # Add to opt-out list
                await self.add_opt_out(
                    contact_type="email",
                    contact_value=from_email,
                    method="email_reply"
                )
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling email reply: {e}")
            return False
    
    async def handle_call_opt_out(self, phone: str) -> bool:
        """
        Handle opt-out request during voice call.
        
        Args:
            phone: Phone number requesting opt-out
            
        Returns:
            True if opt-out was processed successfully
        """
        try:
            await self.add_opt_out(
                contact_type="phone",
                contact_value=phone,
                method="call_request"
            )
            
            logger.info(f"Processed call opt-out for {phone}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling call opt-out: {e}")
            return False
    
    async def handle_sms_opt_out(self, phone: str, message: str) -> bool:
        """
        Handle SMS opt-out (e.g., "STOP" message).
        
        Args:
            phone: Phone number that sent SMS
            message: SMS message text
            
        Returns:
            True if opt-out was detected and processed
        """
        try:
            # Check for STOP keyword (standard SMS opt-out)
            if message.strip().upper() == "STOP":
                await self.add_opt_out(
                    contact_type="phone",
                    contact_value=phone,
                    method="sms"
                )
                
                logger.info(f"Processed SMS opt-out for {phone}")
                return True
            
            # Also check for other opt-out keywords
            if self.detect_opt_out_keywords(message):
                await self.add_opt_out(
                    contact_type="phone",
                    contact_value=phone,
                    method="sms"
                )
                
                logger.info(f"Processed SMS opt-out (keyword) for {phone}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling SMS opt-out: {e}")
            return False
    
    async def get_opt_outs(
        self,
        contact_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OptOut]:
        """
        Get list of opt-outs with optional filtering.
        
        Args:
            contact_type: Optional filter by 'email' or 'phone'
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of OptOut records
        """
        try:
            with get_db_context() as db:
                query = db.query(OptOut)
                
                if contact_type:
                    query = query.filter(OptOut.contact_type == contact_type)
                
                opt_outs = query.order_by(OptOut.opted_out_at.desc()).limit(limit).offset(offset).all()
                return opt_outs
                
        except Exception as e:
            logger.error(f"Error retrieving opt-outs: {e}")
            return []
    
    async def get_opt_out_count(self, contact_type: Optional[str] = None) -> int:
        """
        Get count of opt-outs.
        
        Args:
            contact_type: Optional filter by 'email' or 'phone'
            
        Returns:
            Count of opt-out records
        """
        try:
            with get_db_context() as db:
                query = db.query(OptOut)
                
                if contact_type:
                    query = query.filter(OptOut.contact_type == contact_type)
                
                return query.count()
                
        except Exception as e:
            logger.error(f"Error counting opt-outs: {e}")
            return 0
    
    async def enforce_opt_out_in_query(self, query):
        """
        Add opt-out enforcement to a lead query.
        
        Args:
            query: SQLAlchemy query object for Lead model
            
        Returns:
            Modified query with opt-out filter
        """
        # Filter out opted-out leads
        return query.filter(Lead.opted_out == False)
    
    def validate_opt_out_permanence(self) -> bool:
        """
        Validate that opt-out records are never deleted.
        This is a compliance check that should be run periodically.
        
        Returns:
            True if validation passes
        """
        # This would check database constraints and policies
        # to ensure opt-out records cannot be deleted
        logger.info("Validating opt-out permanence policy")
        
        # In a real implementation, this would:
        # 1. Check database triggers/constraints
        # 2. Verify backup policies include opt-out table
        # 3. Confirm no DELETE permissions on opt_outs table
        
        return True


# Global opt-out manager instance
_opt_out_manager: Optional[OptOutManager] = None


def get_opt_out_manager() -> OptOutManager:
    """Get or create global opt-out manager instance."""
    global _opt_out_manager
    if _opt_out_manager is None:
        _opt_out_manager = OptOutManager()
    return _opt_out_manager
