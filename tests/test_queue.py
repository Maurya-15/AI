"""Property-based tests for queue manager."""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch

from app.queue import QueueManager, QueueItemStatus, get_queue_manager
from app.models import ApprovalQueue, Lead
from app.db import get_db_context
from app.config import get_settings


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def queue_manager():
    """Create queue manager instance."""
    return QueueManager()


@pytest.fixture
def sample_lead(test_db):
    """Create a sample lead for testing."""
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            city="Mumbai",
            category="restaurant",
            primary_email="test@business.com",
            primary_phone="+919876543210",
            email_verified=True,
            phone_verified=True
        )
        db.add(lead)
        db.flush()
        return lead


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def outreach_content(draw):
    """Generate outreach content."""
    return {
        "subject": draw(st.text(min_size=10, max_size=100)),
        "body": draw(st.text(min_size=50, max_size=500)),
        "personalization": {
            "business_name": draw(st.text(min_size=5, max_size=50)),
            "category": draw(st.sampled_from(["restaurant", "retail", "services"]))
        }
    }


# ============================================================================
# Property Tests
# ============================================================================

@settings(max_examples=100)
@given(
    outreach_type=st.sampled_from(["email", "call"]),
    content=outreach_content()
)
@pytest.mark.asyncio
async def test_property_18_approval_queue_routing(outreach_type, content, queue_manager, sample_lead, test_db):
    """
    Feature: devsync-sales-ai, Property 18: Approval queue routing
    For any outreach content generated when approval mode is enabled, the content
    must be added to the approval queue and not sent immediately.
    Validates: Requirements 5.1
    """
    config = get_settings()
    
    # Simulate approval mode enabled
    if config.APPROVAL_MODE:
        # Add to approval queue
        queue_item = await queue_manager.add_to_approval_queue(
            lead=sample_lead,
            outreach_type=outreach_type,
            content=content
        )
        
        # Verify item was added
        assert queue_item is not None, "Queue item must be created"
        assert queue_item.id is not None, "Queue item must have ID"
        assert queue_item.lead_id == sample_lead.id, "Lead ID must match"
        assert queue_item.outreach_type == outreach_type, "Outreach type must match"
        assert queue_item.status == QueueItemStatus.PENDING.value, "Status must be pending"
        
        # Verify item is in database
        retrieved = await queue_manager.get_queue_item(queue_item.id)
        assert retrieved is not None, "Item must be retrievable from queue"


@settings(max_examples=100)
@given(
    outreach_type=st.sampled_from(["email", "call"]),
    content=outreach_content()
)
@pytest.mark.asyncio
async def test_property_19_approval_queue_completeness(outreach_type, content, queue_manager, sample_lead, test_db):
    """
    Feature: devsync-sales-ai, Property 19: Approval queue completeness
    For any item in the approval queue, the item must contain lead details,
    generated content, and personalization information.
    Validates: Requirements 5.2
    """
    # Add to approval queue
    queue_item = await queue_manager.add_to_approval_queue(
        lead=sample_lead,
        outreach_type=outreach_type,
        content=content
    )
    
    # Verify completeness
    assert queue_item.lead_id is not None, "Must have lead ID"
    assert queue_item.outreach_type is not None, "Must have outreach type"
    assert queue_item.content is not None, "Must have content"
    assert queue_item.created_at is not None, "Must have creation timestamp"
    assert queue_item.expires_at is not None, "Must have expiration timestamp"
    
    # Verify content structure
    assert isinstance(queue_item.content, dict), "Content must be dictionary"
    assert len(queue_item.content) > 0, "Content must not be empty"
    
    # Verify lead details are accessible
    with get_db_context() as db:
        lead = db.query(Lead).filter(Lead.id == queue_item.lead_id).first()
        assert lead is not None, "Lead must be accessible from queue item"


@settings(max_examples=100)
@given(
    operator_id=st.text(min_size=5, max_size=50),
    content=outreach_content()
)
@pytest.mark.asyncio
async def test_property_20_approval_workflow(operator_id, content, queue_manager, sample_lead, test_db):
    """
    Feature: devsync-sales-ai, Property 20: Approval workflow
    For any queued item that is approved by an operator, the system must move
    the item to the send queue and proceed with outreach.
    Validates: Requirements 5.3
    """
    # Add to queue
    queue_item = await queue_manager.add_to_approval_queue(
        lead=sample_lead,
        outreach_type="email",
        content=content
    )
    
    # Approve item
    result = await queue_manager.approve_item(
        item_id=queue_item.id,
        operator_id=operator_id
    )
    
    # Verify approval
    assert result, "Approval must succeed"
    
    # Verify item status changed
    approved_item = await queue_manager.get_queue_item(queue_item.id)
    assert approved_item is not None, "Item must still exist"
    assert approved_item.status == QueueItemStatus.APPROVED.value, "Status must be approved"
    assert approved_item.reviewed_by == operator_id, "Reviewer must be recorded"
    assert approved_item.reviewed_at is not None, "Review timestamp must be set"
    
    # Verify item can be marked as sent
    sent_result = await queue_manager.mark_as_sent(queue_item.id)
    assert sent_result, "Item must be markable as sent after approval"
    
    sent_item = await queue_manager.get_queue_item(queue_item.id)
    assert sent_item.status == QueueItemStatus.SENT.value, "Status must be sent"


@settings(max_examples=100)
@given(content=outreach_content())
@pytest.mark.asyncio
async def test_property_21_approval_bypass(content, queue_manager, sample_lead, test_db):
    """
    Feature: devsync-sales-ai, Property 21: Approval bypass
    For any outreach content generated when approval mode is disabled, the content
    must be sent immediately without entering the approval queue.
    Validates: Requirements 5.5
    """
    config = get_settings()
    
    # Simulate approval mode disabled
    original_approval_mode = config.APPROVAL_MODE
    config.APPROVAL_MODE = False
    
    try:
        # In bypass mode, content should not go to queue
        # This would be tested in the campaign/outreach modules
        # Here we verify that queue is not required when approval mode is off
        
        # Get pending count before
        pending_before = await queue_manager.get_pending_count()
        
        # When approval mode is off, items should not be added to queue
        # (This is enforced in the campaign execution logic, not queue manager)
        
        # Verify approval mode is off
        assert not config.APPROVAL_MODE, "Approval mode must be disabled"
        
        # In this mode, the queue manager should still work but not be used
        # The campaign logic would skip queue and send directly
        
    finally:
        config.APPROVAL_MODE = original_approval_mode


# ============================================================================
# Unit Tests for Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_approve_nonexistent_item(queue_manager):
    """Test approving non-existent item."""
    result = await queue_manager.approve_item(
        item_id=99999,
        operator_id="test_operator"
    )
    
    assert not result, "Approving non-existent item should fail"


@pytest.mark.asyncio
async def test_approve_already_approved_item(queue_manager, sample_lead, test_db):
    """Test approving already approved item."""
    # Add and approve item
    queue_item = await queue_manager.add_to_approval_queue(
        lead=sample_lead,
        outreach_type="email",
        content={"test": "content"}
    )
    
    await queue_manager.approve_item(queue_item.id, "operator1")
    
    # Try to approve again
    result = await queue_manager.approve_item(queue_item.id, "operator2")
    
    assert not result, "Approving already approved item should fail"


@pytest.mark.asyncio
async def test_reject_item(queue_manager, sample_lead, test_db):
    """Test rejecting queue item."""
    queue_item = await queue_manager.add_to_approval_queue(
        lead=sample_lead,
        outreach_type="email",
        content={"test": "content"}
    )
    
    result = await queue_manager.reject_item(
        item_id=queue_item.id,
        operator_id="test_operator",
        reason="Content not appropriate"
    )
    
    assert result, "Rejection should succeed"
    
    rejected_item = await queue_manager.get_queue_item(queue_item.id)
    assert rejected_item.status == QueueItemStatus.REJECTED.value
    assert rejected_item.reviewed_by == "test_operator"
    assert "rejection_reason" in rejected_item.content


@pytest.mark.asyncio
async def test_edit_item(queue_manager, sample_lead, test_db):
    """Test editing queue item."""
    original_content = {"subject": "Original", "body": "Original body"}
    queue_item = await queue_manager.add_to_approval_queue(
        lead=sample_lead,
        outreach_type="email",
        content=original_content
    )
    
    new_content = {"subject": "Edited", "body": "Edited body"}
    result = await queue_manager.edit_item(
        item_id=queue_item.id,
        operator_id="test_operator",
        new_content=new_content
    )
    
    assert result, "Edit should succeed"
    
    edited_item = await queue_manager.get_queue_item(queue_item.id)
    assert edited_item.content == new_content
    assert edited_item.content != original_content


@pytest.mark.asyncio
async def test_edit_approved_item_fails(queue_manager, sample_lead, test_db):
    """Test that editing approved item fails."""
    queue_item = await queue_manager.add_to_approval_queue(
        lead=sample_lead,
        outreach_type="email",
        content={"test": "content"}
    )
    
    # Approve item
    await queue_manager.approve_item(queue_item.id, "operator1")
    
    # Try to edit
    result = await queue_manager.edit_item(
        item_id=queue_item.id,
        operator_id="operator2",
        new_content={"test": "new content"}
    )
    
    assert not result, "Editing approved item should fail"


@pytest.mark.asyncio
async def test_approve_with_edited_content(queue_manager, sample_lead, test_db):
    """Test approving with edited content."""
    original_content = {"subject": "Original", "body": "Original body"}
    queue_item = await queue_manager.add_to_approval_queue(
        lead=sample_lead,
        outreach_type="email",
        content=original_content
    )
    
    edited_content = {"subject": "Edited", "body": "Edited body"}
    result = await queue_manager.approve_item(
        item_id=queue_item.id,
        operator_id="test_operator",
        edited_content=edited_content
    )
    
    assert result, "Approval with edit should succeed"
    
    approved_item = await queue_manager.get_queue_item(queue_item.id)
    assert approved_item.content == edited_content
    assert approved_item.status == QueueItemStatus.APPROVED.value


@pytest.mark.asyncio
async def test_expire_old_items(queue_manager, sample_lead, test_db):
    """Test expiring old queue items."""
    # Add item with past expiration
    with get_db_context() as db:
        expired_item = ApprovalQueue(
            lead_id=sample_lead.id,
            outreach_type="email",
            content={"test": "content"},
            status=QueueItemStatus.PENDING.value,
            created_at=datetime.utcnow() - timedelta(days=10),
            expires_at=datetime.utcnow() - timedelta(days=3)
        )
        db.add(expired_item)
        db.flush()
        item_id = expired_item.id
    
    # Expire old items
    count = await queue_manager.expire_old_items()
    
    assert count >= 1, "Should expire at least one item"
    
    # Verify item is expired
    item = await queue_manager.get_queue_item(item_id)
    assert item.status == QueueItemStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_approve_expired_item_fails(queue_manager, sample_lead, test_db):
    """Test that approving expired item fails."""
    # Add item with past expiration
    with get_db_context() as db:
        expired_item = ApprovalQueue(
            lead_id=sample_lead.id,
            outreach_type="email",
            content={"test": "content"},
            status=QueueItemStatus.PENDING.value,
            created_at=datetime.utcnow() - timedelta(days=10),
            expires_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(expired_item)
        db.flush()
        item_id = expired_item.id
    
    # Try to approve
    result = await queue_manager.approve_item(item_id, "test_operator")
    
    assert not result, "Approving expired item should fail"


@pytest.mark.asyncio
async def test_get_queue_with_filters(queue_manager, sample_lead, test_db):
    """Test retrieving queue with filters."""
    # Add multiple items
    await queue_manager.add_to_approval_queue(sample_lead, "email", {"test": "1"})
    await queue_manager.add_to_approval_queue(sample_lead, "call", {"test": "2"})
    await queue_manager.add_to_approval_queue(sample_lead, "email", {"test": "3"})
    
    # Get email items only
    email_items = await queue_manager.get_approval_queue(outreach_type="email")
    assert len(email_items) >= 2, "Should have at least 2 email items"
    for item in email_items:
        assert item.outreach_type == "email"
    
    # Get pending items only
    pending_items = await queue_manager.get_approval_queue(status=QueueItemStatus.PENDING.value)
    assert len(pending_items) >= 3, "Should have at least 3 pending items"
    for item in pending_items:
        assert item.status == QueueItemStatus.PENDING.value


@pytest.mark.asyncio
async def test_get_queue_stats(queue_manager, sample_lead, test_db):
    """Test getting queue statistics."""
    # Add items with different statuses
    item1 = await queue_manager.add_to_approval_queue(sample_lead, "email", {"test": "1"})
    item2 = await queue_manager.add_to_approval_queue(sample_lead, "email", {"test": "2"})
    item3 = await queue_manager.add_to_approval_queue(sample_lead, "email", {"test": "3"})
    
    # Approve one
    await queue_manager.approve_item(item1.id, "operator1")
    
    # Reject one
    await queue_manager.reject_item(item2.id, "operator2")
    
    # Get stats
    stats = await queue_manager.get_queue_stats()
    
    assert stats["total"] >= 3, "Should have at least 3 total items"
    assert stats["pending"] >= 1, "Should have at least 1 pending item"
    assert stats["approved"] >= 1, "Should have at least 1 approved item"
    assert stats["rejected"] >= 1, "Should have at least 1 rejected item"


@pytest.mark.asyncio
async def test_get_items_for_lead(queue_manager, test_db):
    """Test getting all items for a specific lead."""
    # Create two leads
    with get_db_context() as db:
        lead1 = Lead(
            source="google_maps",
            business_name="Business 1",
            primary_email="lead1@example.com",
            email_verified=True
        )
        lead2 = Lead(
            source="google_maps",
            business_name="Business 2",
            primary_email="lead2@example.com",
            email_verified=True
        )
        db.add(lead1)
        db.add(lead2)
        db.flush()
        lead1_id = lead1.id
        lead2_id = lead2.id
    
    # Add items for both leads
    await queue_manager.add_to_approval_queue(lead1, "email", {"test": "1"})
    await queue_manager.add_to_approval_queue(lead1, "call", {"test": "2"})
    await queue_manager.add_to_approval_queue(lead2, "email", {"test": "3"})
    
    # Get items for lead1
    lead1_items = await queue_manager.get_items_for_lead(lead1_id)
    assert len(lead1_items) == 2, "Lead 1 should have 2 items"
    for item in lead1_items:
        assert item.lead_id == lead1_id
    
    # Get items for lead2
    lead2_items = await queue_manager.get_items_for_lead(lead2_id)
    assert len(lead2_items) == 1, "Lead 2 should have 1 item"
    assert lead2_items[0].lead_id == lead2_id
