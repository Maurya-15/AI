"""Queue manager for approval workflow."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum

from app.db import get_db_context
from app.models import ApprovalQueue, Lead, ApprovalStatus
from app.audit import AuditLogger

logger = logging.getLogger(__name__)


class QueueItemStatus(str, Enum):
    """Queue item status enum."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    EXPIRED = "expired"


class QueueManager:
    """Manage approval queue for outreach content."""
    
    # Default expiration period (7 days)
    DEFAULT_EXPIRATION_DAYS = 7
    
    def __init__(self):
        """Initialize queue manager."""
        self.audit = AuditLogger()
    
    async def add_to_approval_queue(
        self,
        lead: Lead,
        outreach_type: str,
        content: Dict[str, Any],
        expires_in_days: Optional[int] = None
    ) -> ApprovalQueue:
        """
        Add item to approval queue.
        
        Args:
            lead: Lead for outreach
            outreach_type: 'email' or 'call'
            content: Outreach content (email body, call script, etc.)
            expires_in_days: Days until expiration (default 7)
            
        Returns:
            Created ApprovalQueue item
        """
        try:
            if expires_in_days is None:
                expires_in_days = self.DEFAULT_EXPIRATION_DAYS
            
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            
            with get_db_context() as db:
                queue_item = ApprovalQueue(
                    lead_id=lead.id,
                    outreach_type=outreach_type,
                    content=content,
                    status=QueueItemStatus.PENDING.value,
                    created_at=datetime.utcnow(),
                    expires_at=expires_at
                )
                db.add(queue_item)
                db.flush()
                
                logger.info(f"Added {outreach_type} for lead {lead.id} to approval queue (ID: {queue_item.id})")
                
                return queue_item
                
        except Exception as e:
            logger.error(f"Error adding to approval queue: {e}")
            await self.audit.log_error(
                component="queue",
                error=e,
                context={"lead_id": lead.id, "outreach_type": outreach_type}
            )
            raise
    
    async def get_approval_queue(
        self,
        status: Optional[str] = None,
        outreach_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_expired: bool = False
    ) -> List[ApprovalQueue]:
        """
        Get approval queue items with optional filtering.
        
        Args:
            status: Filter by status (pending, approved, rejected, sent)
            outreach_type: Filter by type (email, call)
            limit: Maximum items to return
            offset: Number of items to skip
            include_expired: Include expired items
            
        Returns:
            List of ApprovalQueue items
        """
        try:
            with get_db_context() as db:
                query = db.query(ApprovalQueue)
                
                # Filter by status
                if status:
                    query = query.filter(ApprovalQueue.status == status)
                
                # Filter by outreach type
                if outreach_type:
                    query = query.filter(ApprovalQueue.outreach_type == outreach_type)
                
                # Exclude expired items unless requested
                if not include_expired:
                    query = query.filter(ApprovalQueue.expires_at > datetime.utcnow())
                
                # Order by creation date (newest first)
                items = query.order_by(ApprovalQueue.created_at.desc()).limit(limit).offset(offset).all()
                
                return items
                
        except Exception as e:
            logger.error(f"Error retrieving approval queue: {e}")
            return []
    
    async def get_queue_item(self, item_id: int) -> Optional[ApprovalQueue]:
        """
        Get specific queue item by ID.
        
        Args:
            item_id: Queue item ID
            
        Returns:
            ApprovalQueue item or None
        """
        try:
            with get_db_context() as db:
                item = db.query(ApprovalQueue).filter(ApprovalQueue.id == item_id).first()
                return item
        except Exception as e:
            logger.error(f"Error retrieving queue item {item_id}: {e}")
            return None
    
    async def approve_item(
        self,
        item_id: int,
        operator_id: str,
        edited_content: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Approve queue item.
        
        Args:
            item_id: Queue item ID
            operator_id: ID of operator approving
            edited_content: Optional edited content
            
        Returns:
            True if approved successfully
        """
        try:
            with get_db_context() as db:
                item = db.query(ApprovalQueue).filter(ApprovalQueue.id == item_id).first()
                
                if not item:
                    logger.warning(f"Queue item {item_id} not found")
                    return False
                
                # Check if expired
                if item.expires_at < datetime.utcnow():
                    logger.warning(f"Queue item {item_id} has expired")
                    item.status = QueueItemStatus.EXPIRED.value
                    return False
                
                # Check if already processed
                if item.status != QueueItemStatus.PENDING.value:
                    logger.warning(f"Queue item {item_id} already processed (status: {item.status})")
                    return False
                
                # Update item
                item.status = QueueItemStatus.APPROVED.value
                item.reviewed_by = operator_id
                item.reviewed_at = datetime.utcnow()
                
                # Update content if edited
                if edited_content:
                    item.content = edited_content
                
                logger.info(f"Approved queue item {item_id} by operator {operator_id}")
                
                # Audit log
                await self.audit.log_approval(
                    approval_id=item_id,
                    action="approve",
                    user_id=operator_id,
                    lead_id=item.lead_id
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error approving queue item {item_id}: {e}")
            await self.audit.log_error(
                component="queue",
                error=e,
                context={"item_id": item_id, "operator_id": operator_id}
            )
            return False
    
    async def reject_item(
        self,
        item_id: int,
        operator_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Reject queue item.
        
        Args:
            item_id: Queue item ID
            operator_id: ID of operator rejecting
            reason: Optional rejection reason
            
        Returns:
            True if rejected successfully
        """
        try:
            with get_db_context() as db:
                item = db.query(ApprovalQueue).filter(ApprovalQueue.id == item_id).first()
                
                if not item:
                    logger.warning(f"Queue item {item_id} not found")
                    return False
                
                # Check if already processed
                if item.status != QueueItemStatus.PENDING.value:
                    logger.warning(f"Queue item {item_id} already processed (status: {item.status})")
                    return False
                
                # Update item
                item.status = QueueItemStatus.REJECTED.value
                item.reviewed_by = operator_id
                item.reviewed_at = datetime.utcnow()
                
                # Store rejection reason in content
                if reason:
                    if not item.content:
                        item.content = {}
                    item.content['rejection_reason'] = reason
                
                logger.info(f"Rejected queue item {item_id} by operator {operator_id}")
                
                # Audit log
                await self.audit.log_approval(
                    approval_id=item_id,
                    action="reject",
                    user_id=operator_id,
                    lead_id=item.lead_id
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error rejecting queue item {item_id}: {e}")
            await self.audit.log_error(
                component="queue",
                error=e,
                context={"item_id": item_id, "operator_id": operator_id}
            )
            return False
    
    async def edit_item(
        self,
        item_id: int,
        operator_id: str,
        new_content: Dict[str, Any]
    ) -> bool:
        """
        Edit queue item content.
        
        Args:
            item_id: Queue item ID
            operator_id: ID of operator editing
            new_content: New content
            
        Returns:
            True if edited successfully
        """
        try:
            with get_db_context() as db:
                item = db.query(ApprovalQueue).filter(ApprovalQueue.id == item_id).first()
                
                if not item:
                    logger.warning(f"Queue item {item_id} not found")
                    return False
                
                # Check if expired
                if item.expires_at < datetime.utcnow():
                    logger.warning(f"Queue item {item_id} has expired")
                    return False
                
                # Only allow editing pending items
                if item.status != QueueItemStatus.PENDING.value:
                    logger.warning(f"Cannot edit non-pending item {item_id} (status: {item.status})")
                    return False
                
                # Update content
                item.content = new_content
                
                logger.info(f"Edited queue item {item_id} by operator {operator_id}")
                
                # Audit log
                await self.audit.log_approval(
                    approval_id=item_id,
                    action="edit",
                    user_id=operator_id,
                    lead_id=item.lead_id
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error editing queue item {item_id}: {e}")
            return False
    
    async def mark_as_sent(self, item_id: int) -> bool:
        """
        Mark queue item as sent.
        
        Args:
            item_id: Queue item ID
            
        Returns:
            True if marked successfully
        """
        try:
            with get_db_context() as db:
                item = db.query(ApprovalQueue).filter(ApprovalQueue.id == item_id).first()
                
                if not item:
                    logger.warning(f"Queue item {item_id} not found")
                    return False
                
                # Only mark approved items as sent
                if item.status != QueueItemStatus.APPROVED.value:
                    logger.warning(f"Cannot mark non-approved item {item_id} as sent (status: {item.status})")
                    return False
                
                item.status = QueueItemStatus.SENT.value
                
                logger.info(f"Marked queue item {item_id} as sent")
                
                return True
                
        except Exception as e:
            logger.error(f"Error marking queue item {item_id} as sent: {e}")
            return False
    
    async def expire_old_items(self) -> int:
        """
        Expire old queue items that have passed their expiration date.
        
        Returns:
            Number of items expired
        """
        try:
            with get_db_context() as db:
                # Find expired pending items
                expired_items = db.query(ApprovalQueue).filter(
                    ApprovalQueue.status == QueueItemStatus.PENDING.value,
                    ApprovalQueue.expires_at < datetime.utcnow()
                ).all()
                
                count = 0
                for item in expired_items:
                    item.status = QueueItemStatus.EXPIRED.value
                    count += 1
                
                if count > 0:
                    logger.info(f"Expired {count} old queue items")
                
                return count
                
        except Exception as e:
            logger.error(f"Error expiring old queue items: {e}")
            return 0
    
    async def get_queue_stats(self) -> Dict[str, int]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with queue stats
        """
        try:
            with get_db_context() as db:
                total = db.query(ApprovalQueue).count()
                pending = db.query(ApprovalQueue).filter(
                    ApprovalQueue.status == QueueItemStatus.PENDING.value
                ).count()
                approved = db.query(ApprovalQueue).filter(
                    ApprovalQueue.status == QueueItemStatus.APPROVED.value
                ).count()
                rejected = db.query(ApprovalQueue).filter(
                    ApprovalQueue.status == QueueItemStatus.REJECTED.value
                ).count()
                sent = db.query(ApprovalQueue).filter(
                    ApprovalQueue.status == QueueItemStatus.SENT.value
                ).count()
                expired = db.query(ApprovalQueue).filter(
                    ApprovalQueue.status == QueueItemStatus.EXPIRED.value
                ).count()
                
                return {
                    "total": total,
                    "pending": pending,
                    "approved": approved,
                    "rejected": rejected,
                    "sent": sent,
                    "expired": expired
                }
                
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}
    
    async def get_pending_count(self) -> int:
        """
        Get count of pending items.
        
        Returns:
            Number of pending items
        """
        try:
            with get_db_context() as db:
                return db.query(ApprovalQueue).filter(
                    ApprovalQueue.status == QueueItemStatus.PENDING.value,
                    ApprovalQueue.expires_at > datetime.utcnow()
                ).count()
        except Exception as e:
            logger.error(f"Error getting pending count: {e}")
            return 0
    
    async def get_items_for_lead(self, lead_id: int) -> List[ApprovalQueue]:
        """
        Get all queue items for a specific lead.
        
        Args:
            lead_id: Lead ID
            
        Returns:
            List of queue items for the lead
        """
        try:
            with get_db_context() as db:
                items = db.query(ApprovalQueue).filter(
                    ApprovalQueue.lead_id == lead_id
                ).order_by(ApprovalQueue.created_at.desc()).all()
                
                return items
        except Exception as e:
            logger.error(f"Error getting items for lead {lead_id}: {e}")
            return []


# Global queue manager instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager() -> QueueManager:
    """Get or create global queue manager instance."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager()
    return _queue_manager
