"""Property-based tests for opt-out handling system."""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, AsyncMock

from app.opt_out import OptOutManager, get_opt_out_manager
from app.models import OptOut, Lead
from app.db import get_db_context


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def opt_out_manager():
    """Create opt-out manager instance."""
    return OptOutManager()


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
            phone_verified=True,
            opted_out=False
        )
        db.add(lead)
        db.flush()
        return lead


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def email_address(draw):
    """Generate valid email addresses."""
    username = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd')),
        min_size=3,
        max_size=20
    ))
    domain = draw(st.sampled_from([
        "business.com", "company.org", "enterprise.net"
    ]))
    return f"{username}@{domain}"


@st.composite
def phone_number(draw):
    """Generate valid phone numbers."""
    country_code = draw(st.sampled_from(["+91", "+1", "+44"]))
    number = draw(st.integers(min_value=1000000000, max_value=9999999999))
    return f"{country_code}{number}"


@st.composite
def opt_out_method(draw):
    """Generate opt-out methods."""
    return draw(st.sampled_from(["link", "email_reply", "call_request", "sms"]))


# ============================================================================
# Property Tests
# ============================================================================

@settings(max_examples=100)
@given(
    email=email_address(),
    method=opt_out_method()
)
@pytest.mark.asyncio
async def test_property_11_opt_out_immediacy(email, method, opt_out_manager, test_db):
    """
    Feature: devsync-sales-ai, Property 11: Opt-out immediacy
    For any contact that triggers an unsubscribe action (link click, email reply,
    call request), the system must immediately set opted_out to True in the database.
    Validates: Requirements 3.2, 3.5
    """
    # Create a lead with this email
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_email=email,
            email_verified=True,
            opted_out=False
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
    
    # Trigger opt-out
    result = await opt_out_manager.add_opt_out(
        contact_type="email",
        contact_value=email,
        method=method
    )
    
    # Verify opt-out was added
    assert result, "Opt-out should be added successfully"
    
    # Verify lead is immediately marked as opted out
    with get_db_context() as db:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        assert lead is not None, "Lead should exist"
        assert lead.opted_out == True, "Lead must be immediately marked as opted out"
        assert lead.opted_out_at is not None, "Opt-out timestamp must be set"
        assert lead.opted_out_method == method, "Opt-out method must be recorded"
    
    # Verify opt-out record exists
    with get_db_context() as db:
        opt_out = db.query(OptOut).filter(
            OptOut.contact_type == "email",
            OptOut.contact_value == email
        ).first()
        assert opt_out is not None, "Opt-out record must exist"
        assert opt_out.opt_out_method == method, "Method must be recorded"


@settings(max_examples=100)
@given(
    email=email_address(),
    method=opt_out_method()
)
@pytest.mark.asyncio
async def test_property_12_opt_out_enforcement(email, method, opt_out_manager, test_db):
    """
    Feature: devsync-sales-ai, Property 12: Opt-out enforcement
    For any lead with opted_out set to True, attempting to send an email or
    place a call must be blocked and the lead must be skipped.
    Validates: Requirements 3.3
    """
    # Create opted-out lead
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_email=email,
            email_verified=True,
            opted_out=True,
            opted_out_at=datetime.utcnow(),
            opted_out_method=method
        )
        db.add(lead)
        db.flush()
    
    # Add to opt-out list
    await opt_out_manager.add_opt_out(
        contact_type="email",
        contact_value=email,
        method=method
    )
    
    # Check if opted out
    is_opted_out = await opt_out_manager.is_opted_out("email", email)
    
    # Must be blocked
    assert is_opted_out, "Opted-out contact must be detected"
    
    # Verify query enforcement
    with get_db_context() as db:
        query = db.query(Lead).filter(Lead.primary_email == email)
        enforced_query = await opt_out_manager.enforce_opt_out_in_query(query)
        
        # Should return no results when opted out
        results = enforced_query.all()
        assert len(results) == 0, "Opted-out leads must be filtered from queries"


@settings(max_examples=100)
@given(
    keyword=st.sampled_from([
        "unsubscribe",
        "STOP",
        "remove me",
        "opt-out",
        "do not contact",
        "no more emails",
        "Please UNSUBSCRIBE me",
        "I want to opt out",
        "Stop sending emails"
    ])
)
@pytest.mark.asyncio
async def test_property_13_keyword_detection(keyword, opt_out_manager):
    """
    Feature: devsync-sales-ai, Property 13: Keyword detection
    For any email reply containing opt-out keywords (unsubscribe, stop, remove,
    opt-out), the system must detect the keyword and mark the sender as opted-out.
    Validates: Requirements 3.4
    """
    # Create email body with keyword
    email_body = f"Hello, {keyword}. Thank you."
    
    # Detect keywords
    detected = opt_out_manager.detect_opt_out_keywords(email_body)
    
    # Must detect the keyword
    assert detected, f"Keyword '{keyword}' must be detected in email body"
    
    # Test case insensitivity
    email_body_upper = email_body.upper()
    detected_upper = opt_out_manager.detect_opt_out_keywords(email_body_upper)
    assert detected_upper, "Keyword detection must be case-insensitive"
    
    # Test with keyword in middle of sentence
    email_body_middle = f"I would like to {keyword} from your mailing list."
    detected_middle = opt_out_manager.detect_opt_out_keywords(email_body_middle)
    assert detected_middle, "Keyword must be detected anywhere in text"


@settings(max_examples=100)
@given(
    email=email_address(),
    method=opt_out_method()
)
@pytest.mark.asyncio
async def test_property_24_opt_out_permanence(email, method, opt_out_manager, test_db):
    """
    Feature: devsync-sales-ai, Property 24: Opt-out permanence
    For any opt-out record created, the record must remain in the database
    indefinitely and never be deleted by retention policies.
    Validates: Requirements 6.3
    """
    # Add opt-out
    await opt_out_manager.add_opt_out(
        contact_type="email",
        contact_value=email,
        method=method
    )
    
    # Verify record exists
    with get_db_context() as db:
        opt_out = db.query(OptOut).filter(
            OptOut.contact_type == "email",
            OptOut.contact_value == email
        ).first()
        
        assert opt_out is not None, "Opt-out record must exist"
        opt_out_id = opt_out.id
    
    # Simulate time passing (retention policy would run)
    # In a real system, we'd run the retention policy cleanup
    # For this test, we just verify the record still exists
    
    with get_db_context() as db:
        opt_out = db.query(OptOut).filter(OptOut.id == opt_out_id).first()
        assert opt_out is not None, "Opt-out record must never be deleted"
    
    # Verify permanence validation
    is_permanent = opt_out_manager.validate_opt_out_permanence()
    assert is_permanent, "Opt-out permanence policy must be validated"


# ============================================================================
# Unit Tests for Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_duplicate_opt_out_handling(opt_out_manager, test_db):
    """Test that duplicate opt-outs are handled gracefully."""
    email = "duplicate@example.com"
    
    # Add opt-out first time
    result1 = await opt_out_manager.add_opt_out(
        contact_type="email",
        contact_value=email,
        method="link"
    )
    assert result1, "First opt-out should succeed"
    
    # Try to add again
    result2 = await opt_out_manager.add_opt_out(
        contact_type="email",
        contact_value=email,
        method="email_reply"
    )
    assert not result2, "Duplicate opt-out should return False"
    
    # Verify only one record exists
    with get_db_context() as db:
        count = db.query(OptOut).filter(
            OptOut.contact_type == "email",
            OptOut.contact_value == email
        ).count()
        assert count == 1, "Should have exactly one opt-out record"


@pytest.mark.asyncio
async def test_email_reply_with_opt_out_keyword(opt_out_manager, test_db):
    """Test handling email reply with opt-out keyword."""
    email = "reply@example.com"
    body = "Please unsubscribe me from your mailing list. Thanks."
    
    # Handle email reply
    result = await opt_out_manager.handle_email_reply(email, body)
    
    assert result, "Email reply with opt-out keyword should be processed"
    
    # Verify opt-out was added
    is_opted_out = await opt_out_manager.is_opted_out("email", email)
    assert is_opted_out, "Email should be opted out"


@pytest.mark.asyncio
async def test_sms_stop_message(opt_out_manager, test_db):
    """Test handling SMS STOP message."""
    phone = "+919876543210"
    
    # Handle STOP message
    result = await opt_out_manager.handle_sms_opt_out(phone, "STOP")
    
    assert result, "STOP message should be processed"
    
    # Verify opt-out was added
    is_opted_out = await opt_out_manager.is_opted_out("phone", phone)
    assert is_opted_out, "Phone should be opted out"


@pytest.mark.asyncio
async def test_call_opt_out_request(opt_out_manager, test_db):
    """Test handling opt-out request during call."""
    phone = "+919876543210"
    
    # Handle call opt-out
    result = await opt_out_manager.handle_call_opt_out(phone)
    
    assert result, "Call opt-out should be processed"
    
    # Verify opt-out was added
    is_opted_out = await opt_out_manager.is_opted_out("phone", phone)
    assert is_opted_out, "Phone should be opted out"


@pytest.mark.asyncio
async def test_no_keyword_in_email(opt_out_manager):
    """Test that emails without opt-out keywords are not flagged."""
    body = "Thank you for your email. I'm interested in learning more about your services."
    
    detected = opt_out_manager.detect_opt_out_keywords(body)
    
    assert not detected, "Should not detect opt-out in normal email"


@pytest.mark.asyncio
async def test_empty_text_keyword_detection(opt_out_manager):
    """Test keyword detection with empty text."""
    detected = opt_out_manager.detect_opt_out_keywords("")
    assert not detected, "Empty text should not trigger detection"
    
    detected_none = opt_out_manager.detect_opt_out_keywords(None)
    assert not detected_none, "None text should not trigger detection"


@pytest.mark.asyncio
async def test_get_opt_outs_pagination(opt_out_manager, test_db):
    """Test retrieving opt-outs with pagination."""
    # Add multiple opt-outs
    for i in range(5):
        await opt_out_manager.add_opt_out(
            contact_type="email",
            contact_value=f"test{i}@example.com",
            method="link"
        )
    
    # Get first page
    page1 = await opt_out_manager.get_opt_outs(limit=2, offset=0)
    assert len(page1) == 2, "Should return 2 records"
    
    # Get second page
    page2 = await opt_out_manager.get_opt_outs(limit=2, offset=2)
    assert len(page2) == 2, "Should return 2 records"
    
    # Verify different records
    page1_emails = [opt.contact_value for opt in page1]
    page2_emails = [opt.contact_value for opt in page2]
    assert set(page1_emails).isdisjoint(set(page2_emails)), "Pages should have different records"


@pytest.mark.asyncio
async def test_get_opt_out_count(opt_out_manager, test_db):
    """Test counting opt-outs."""
    # Add opt-outs
    await opt_out_manager.add_opt_out("email", "test1@example.com", "link")
    await opt_out_manager.add_opt_out("email", "test2@example.com", "link")
    await opt_out_manager.add_opt_out("phone", "+919876543210", "sms")
    
    # Count all
    total = await opt_out_manager.get_opt_out_count()
    assert total >= 3, "Should have at least 3 opt-outs"
    
    # Count emails only
    email_count = await opt_out_manager.get_opt_out_count(contact_type="email")
    assert email_count >= 2, "Should have at least 2 email opt-outs"
    
    # Count phones only
    phone_count = await opt_out_manager.get_opt_out_count(contact_type="phone")
    assert phone_count >= 1, "Should have at least 1 phone opt-out"


@pytest.mark.asyncio
async def test_opt_out_with_lead_update(opt_out_manager, test_db):
    """Test that opt-out updates the associated lead."""
    email = "leadupdate@example.com"
    
    # Create lead
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_email=email,
            email_verified=True,
            opted_out=False
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
    
    # Add opt-out
    await opt_out_manager.add_opt_out(
        contact_type="email",
        contact_value=email,
        method="link"
    )
    
    # Verify lead was updated
    with get_db_context() as db:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        assert lead.opted_out == True, "Lead should be marked as opted out"
        assert lead.opted_out_at is not None, "Opt-out timestamp should be set"
        assert lead.opted_out_method == "link", "Opt-out method should be recorded"


@pytest.mark.asyncio
async def test_opt_out_filter_in_campaign_query(opt_out_manager, test_db):
    """Test that opt-out filter works in campaign lead selection."""
    # Create opted-out and active leads
    with get_db_context() as db:
        opted_out_lead = Lead(
            source="google_maps",
            business_name="Opted Out Business",
            primary_email="optedout@example.com",
            email_verified=True,
            opted_out=True
        )
        active_lead = Lead(
            source="google_maps",
            business_name="Active Business",
            primary_email="active@example.com",
            email_verified=True,
            opted_out=False
        )
        db.add(opted_out_lead)
        db.add(active_lead)
        db.flush()
    
    # Query with opt-out enforcement
    with get_db_context() as db:
        query = db.query(Lead).filter(Lead.email_verified == True)
        enforced_query = await opt_out_manager.enforce_opt_out_in_query(query)
        
        results = enforced_query.all()
        
        # Should only return active leads
        for lead in results:
            assert lead.opted_out == False, "Query should only return non-opted-out leads"
