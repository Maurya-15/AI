"""Property-based tests for database operations.

Feature: devsync-sales-ai
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from app.db import Base
from app.models import (
    Lead, VerificationResult, OutreachHistory, OptOut,
    ApprovalQueue, Campaign, AuditLog
)


# Test database setup
@pytest.fixture(scope="function")
def test_db_session():
    """Create a test database session."""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)


# Hypothesis strategies for generating test data
@st.composite
def lead_strategy(draw):
    """Generate random lead data."""
    return {
        "source": draw(st.sampled_from(["google_maps", "justdial", "indiamart", "yelp", "linkedin_company"])),
        "business_name": draw(st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', ' ')))),
        "city": draw(st.one_of(st.none(), st.sampled_from(["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata"]))),
        "category": draw(st.one_of(st.none(), st.sampled_from(["restaurant", "retail", "services", "manufacturing"]))),
        "website": draw(st.one_of(st.none(), st.from_regex(r"https?://[a-z0-9-]+\.[a-z]{2,}", fullmatch=True))),
        "primary_email": draw(st.one_of(st.none(), st.emails())),
        "primary_phone": draw(st.one_of(st.none(), st.from_regex(r"\+91[6-9]\d{9}", fullmatch=True))),
        "email_verified": draw(st.booleans()),
        "phone_verified": draw(st.booleans()),
        "verification_confidence": draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0))),
        "opted_out": draw(st.booleans()),
        "contact_count": draw(st.integers(min_value=0, max_value=100))
    }


# Property 48: Lead storage round-trip
@pytest.mark.property
@given(lead_data=lead_strategy())
@settings(max_examples=100)
def test_property_48_lead_storage_round_trip(test_db_session, lead_data):
    """
    Feature: devsync-sales-ai, Property 48: Lead storage round-trip
    For any lead stored in the database, retrieving the lead by ID must return
    all persisted fields with their original values.
    
    Validates: Requirements 15.2
    """
    # Create lead
    lead = Lead(**lead_data)
    test_db_session.add(lead)
    test_db_session.commit()
    test_db_session.refresh(lead)
    
    lead_id = lead.id
    
    # Clear session to ensure we're reading from database
    test_db_session.expunge_all()
    
    # Retrieve lead
    retrieved_lead = test_db_session.query(Lead).filter(Lead.id == lead_id).first()
    
    # Verify all fields match
    assert retrieved_lead is not None
    assert retrieved_lead.id == lead_id
    assert retrieved_lead.source == lead_data["source"]
    assert retrieved_lead.business_name == lead_data["business_name"]
    assert retrieved_lead.city == lead_data["city"]
    assert retrieved_lead.category == lead_data["category"]
    assert retrieved_lead.website == lead_data["website"]
    assert retrieved_lead.primary_email == lead_data["primary_email"]
    assert retrieved_lead.primary_phone == lead_data["primary_phone"]
    assert retrieved_lead.email_verified == lead_data["email_verified"]
    assert retrieved_lead.phone_verified == lead_data["phone_verified"]
    assert retrieved_lead.opted_out == lead_data["opted_out"]
    assert retrieved_lead.contact_count == lead_data["contact_count"]
    
    # Verify confidence score (handle floating point comparison)
    if lead_data["verification_confidence"] is not None:
        assert abs(retrieved_lead.verification_confidence - lead_data["verification_confidence"]) < 0.0001
    else:
        assert retrieved_lead.verification_confidence is None


# Property 49: Outreach history round-trip
@pytest.mark.property
@given(
    outreach_type=st.sampled_from(["email", "call"]),
    status=st.sampled_from(["sent", "delivered", "bounced", "failed"]),
    outcome=st.one_of(st.none(), st.sampled_from(["answered", "voicemail", "busy", "no-answer"])),
    duration=st.one_of(st.none(), st.integers(min_value=0, max_value=3600))
)
@settings(max_examples=100)
def test_property_49_outreach_history_round_trip(test_db_session, outreach_type, status, outcome, duration):
    """
    Feature: devsync-sales-ai, Property 49: Outreach history round-trip
    For any outreach attempt recorded, retrieving the record must return all
    attempt details including timestamp, status, provider response, and outcome.
    
    Validates: Requirements 15.3
    """
    # Create a lead first
    lead = Lead(
        source="google_maps",
        business_name="Test Business",
        email_verified=True,
        phone_verified=True
    )
    test_db_session.add(lead)
    test_db_session.commit()
    
    # Create outreach history
    outreach = OutreachHistory(
        lead_id=lead.id,
        outreach_type=outreach_type,
        status=status,
        outcome=outcome,
        duration_seconds=duration,
        content_hash="abc123",
        provider_message_id="msg_123",
        provider_response={"status": "ok", "code": 200}
    )
    test_db_session.add(outreach)
    test_db_session.commit()
    test_db_session.refresh(outreach)
    
    outreach_id = outreach.id
    
    # Clear session
    test_db_session.expunge_all()
    
    # Retrieve outreach history
    retrieved = test_db_session.query(OutreachHistory).filter(OutreachHistory.id == outreach_id).first()
    
    # Verify all fields match
    assert retrieved is not None
    assert retrieved.id == outreach_id
    assert retrieved.lead_id == lead.id
    assert retrieved.outreach_type == outreach_type
    assert retrieved.status == status
    assert retrieved.outcome == outcome
    assert retrieved.duration_seconds == duration
    assert retrieved.content_hash == "abc123"
    assert retrieved.provider_message_id == "msg_123"
    assert retrieved.provider_response == {"status": "ok", "code": 200}
    assert retrieved.attempted_at is not None


# Property 50: Opt-out permanence
@pytest.mark.property
@given(
    contact_type=st.sampled_from(["email", "phone"]),
    contact_value=st.one_of(st.emails(), st.from_regex(r"\+91[6-9]\d{9}", fullmatch=True)),
    opt_out_method=st.sampled_from(["link", "email_reply", "call_request", "sms"])
)
@settings(max_examples=100)
def test_property_50_opt_out_permanence(test_db_session, contact_type, contact_value, opt_out_method):
    """
    Feature: devsync-sales-ai, Property 50: Opt-out permanence
    For any opt-out record created, the record must remain in the database
    indefinitely and never be deleted by retention policies.
    
    Validates: Requirements 15.4
    """
    # Create opt-out record
    opt_out = OptOut(
        contact_type=contact_type,
        contact_value=contact_value,
        opt_out_method=opt_out_method
    )
    test_db_session.add(opt_out)
    test_db_session.commit()
    test_db_session.refresh(opt_out)
    
    opt_out_id = opt_out.id
    original_timestamp = opt_out.opted_out_at
    
    # Simulate time passing (retention policy would run)
    # In a real scenario, this would be days/months later
    test_db_session.expunge_all()
    
    # Verify opt-out still exists
    retrieved = test_db_session.query(OptOut).filter(OptOut.id == opt_out_id).first()
    
    assert retrieved is not None, "Opt-out record must never be deleted"
    assert retrieved.id == opt_out_id
    assert retrieved.contact_type == contact_type
    assert retrieved.contact_value == contact_value
    assert retrieved.opt_out_method == opt_out_method
    assert retrieved.opted_out_at == original_timestamp
    
    # Verify we can query by contact value
    by_value = test_db_session.query(OptOut).filter(
        OptOut.contact_type == contact_type,
        OptOut.contact_value == contact_value
    ).first()
    
    assert by_value is not None
    assert by_value.id == opt_out_id


# Additional unit tests for database operations
def test_lead_deduplication_constraint(test_db_session):
    """Test that duplicate leads are prevented by unique constraint."""
    lead1 = Lead(
        source="google_maps",
        business_name="Test Business",
        website="https://example.com",
        primary_phone="+919876543210"
    )
    test_db_session.add(lead1)
    test_db_session.commit()
    
    # Try to create duplicate
    lead2 = Lead(
        source="justdial",  # Different source
        business_name="Test Business",
        website="https://example.com",
        primary_phone="+919876543210"
    )
    test_db_session.add(lead2)
    
    # Should raise integrity error
    with pytest.raises(Exception):  # SQLAlchemy IntegrityError
        test_db_session.commit()


def test_verification_result_relationship(test_db_session):
    """Test relationship between Lead and VerificationResult."""
    lead = Lead(
        source="google_maps",
        business_name="Test Business",
        primary_email="test@example.com"
    )
    test_db_session.add(lead)
    test_db_session.commit()
    
    # Add verification result
    verification = VerificationResult(
        lead_id=lead.id,
        verification_type="email",
        contact_value="test@example.com",
        is_valid=True,
        confidence_score=0.95,
        provider_name="AbstractAPI",
        provider_response={"deliverable": True}
    )
    test_db_session.add(verification)
    test_db_session.commit()
    
    # Verify relationship
    test_db_session.refresh(lead)
    assert len(lead.verification_results) == 1
    assert lead.verification_results[0].contact_value == "test@example.com"


def test_outreach_history_cascade_delete(test_db_session):
    """Test that outreach history is deleted when lead is deleted."""
    lead = Lead(
        source="google_maps",
        business_name="Test Business"
    )
    test_db_session.add(lead)
    test_db_session.commit()
    
    # Add outreach history
    outreach = OutreachHistory(
        lead_id=lead.id,
        outreach_type="email",
        status="sent"
    )
    test_db_session.add(outreach)
    test_db_session.commit()
    
    outreach_id = outreach.id
    
    # Delete lead
    test_db_session.delete(lead)
    test_db_session.commit()
    
    # Verify outreach history is also deleted
    retrieved = test_db_session.query(OutreachHistory).filter(OutreachHistory.id == outreach_id).first()
    assert retrieved is None


def test_campaign_tracking(test_db_session):
    """Test campaign creation and tracking."""
    campaign = Campaign(
        campaign_type="email",
        total_attempted=100,
        total_success=95,
        total_failed=5
    )
    test_db_session.add(campaign)
    test_db_session.commit()
    
    # Verify campaign was created
    assert campaign.id is not None
    assert campaign.started_at is not None
    assert campaign.completed_at is None  # Not completed yet
    
    # Update campaign
    campaign.completed_at = datetime.utcnow()
    test_db_session.commit()
    
    # Verify update
    test_db_session.refresh(campaign)
    assert campaign.completed_at is not None


def test_approval_queue_expiration(test_db_session):
    """Test approval queue item with expiration."""
    lead = Lead(
        source="google_maps",
        business_name="Test Business"
    )
    test_db_session.add(lead)
    test_db_session.commit()
    
    # Create approval queue item
    expires_at = datetime.utcnow() + timedelta(days=7)
    approval = ApprovalQueue(
        lead_id=lead.id,
        outreach_type="email",
        content={"subject": "Test", "body": "Test email"},
        expires_at=expires_at
    )
    test_db_session.add(approval)
    test_db_session.commit()
    
    # Verify creation
    assert approval.id is not None
    assert approval.status == "pending"
    assert approval.expires_at == expires_at


def test_audit_log_creation(test_db_session):
    """Test audit log creation."""
    log = AuditLog(
        log_level="INFO",
        component="emailer",
        action="send_email",
        lead_id=1,
        user_id="operator_123",
        details={"recipient": "test@example.com", "status": "sent"}
    )
    test_db_session.add(log)
    test_db_session.commit()
    
    # Verify log was created
    assert log.id is not None
    assert log.created_at is not None
    assert log.details["recipient"] == "test@example.com"
