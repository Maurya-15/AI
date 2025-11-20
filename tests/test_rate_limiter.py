"""Property-based tests for rate limiter."""

import pytest
from datetime import datetime, timedelta, date
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch

from app.rate_limiter import RateLimiter, get_rate_limiter
from app.models import Lead, OutreachHistory
from app.db import get_db_context
from app.config import get_settings


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def rate_limiter():
    """Create rate limiter instance."""
    limiter = RateLimiter()
    # Reset counts for clean state
    limiter._daily_counts.clear()
    limiter._domain_counts.clear()
    return limiter


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
# Property Tests
# ============================================================================

@settings(max_examples=100)
@given(email_count=st.integers(min_value=0, max_value=150))
@pytest.mark.asyncio
async def test_property_14_daily_email_cap_enforcement(email_count, rate_limiter, test_db):
    """
    Feature: devsync-sales-ai, Property 14: Daily email cap enforcement
    For any daily email campaign, the total number of emails sent must not
    exceed the configured DAILY_EMAIL_CAP.
    Validates: Requirements 4.1
    """
    config = get_settings()
    cap = config.DAILY_EMAIL_CAP
    
    # Create email history records for today
    today = datetime.combine(date.today(), datetime.min.time())
    
    with get_db_context() as db:
        # Create a lead
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_email="test@example.com",
            email_verified=True
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
        
        # Add email history records
        for i in range(min(email_count, cap + 10)):  # Cap at reasonable number
            history = OutreachHistory(
                lead_id=lead_id,
                outreach_type="email",
                status="sent",
                attempted_at=today + timedelta(minutes=i)
            )
            db.add(history)
        db.flush()
    
    # Check cap
    can_send, sent_today, remaining = await rate_limiter.check_daily_email_cap()
    
    # Verify cap enforcement
    if email_count >= cap:
        assert not can_send, f"Should not allow sending when {sent_today} >= {cap}"
        assert remaining == 0, "Remaining should be 0 when cap reached"
    else:
        assert can_send, f"Should allow sending when {sent_today} < {cap}"
        assert remaining > 0, "Remaining should be positive when under cap"
    
    # Verify sent count matches
    assert sent_today == min(email_count, cap + 10), "Sent count should match history"


@settings(max_examples=100)
@given(call_count=st.integers(min_value=0, max_value=150))
@pytest.mark.asyncio
async def test_property_15_daily_call_cap_enforcement(call_count, rate_limiter, test_db):
    """
    Feature: devsync-sales-ai, Property 15: Daily call cap enforcement
    For any daily call campaign, the total number of calls placed must not
    exceed the configured DAILY_CALL_CAP.
    Validates: Requirements 4.2
    """
    config = get_settings()
    cap = config.DAILY_CALL_CAP
    
    # Create call history records for today
    today = datetime.combine(date.today(), datetime.min.time())
    
    with get_db_context() as db:
        # Create a lead
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_phone="+919876543210",
            phone_verified=True
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
        
        # Add call history records
        for i in range(min(call_count, cap + 10)):
            history = OutreachHistory(
                lead_id=lead_id,
                outreach_type="call",
                status="completed",
                attempted_at=today + timedelta(minutes=i)
            )
            db.add(history)
        db.flush()
    
    # Check cap
    can_send, calls_today, remaining = await rate_limiter.check_daily_call_cap()
    
    # Verify cap enforcement
    if call_count >= cap:
        assert not can_send, f"Should not allow calling when {calls_today} >= {cap}"
        assert remaining == 0, "Remaining should be 0 when cap reached"
    else:
        assert can_send, f"Should allow calling when {calls_today} < {cap}"
        assert remaining > 0, "Remaining should be positive when under cap"


@settings(max_examples=100)
@given(days_since_contact=st.integers(min_value=0, max_value=60))
@pytest.mark.asyncio
async def test_property_17_cooldown_enforcement(days_since_contact, rate_limiter, test_db):
    """
    Feature: devsync-sales-ai, Property 17: Cooldown enforcement
    For any lead that has been contacted, attempting to contact the same lead
    again before the cooldown period (default 30 days) expires must be blocked.
    Validates: Requirements 4.5
    """
    config = get_settings()
    cooldown_days = config.COOLDOWN_DAYS
    
    # Create lead with last contact date
    with get_db_context() as db:
        last_contact = datetime.utcnow() - timedelta(days=days_since_contact)
        
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_email="test@example.com",
            email_verified=True,
            last_contacted_at=last_contact,
            contact_count=1
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
    
    # Check cooldown
    can_contact, last_contacted = await rate_limiter.check_cooldown(lead_id)
    
    # Verify cooldown enforcement
    if days_since_contact < cooldown_days:
        assert not can_contact, f"Should block contact within {cooldown_days} days (contacted {days_since_contact} days ago)"
    else:
        assert can_contact, f"Should allow contact after {cooldown_days} days (contacted {days_since_contact} days ago)"
    
    assert last_contacted is not None, "Last contacted timestamp should be returned"


# ============================================================================
# Unit Tests for Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_never_contacted_lead_allowed(rate_limiter, test_db):
    """Test that leads never contacted are allowed."""
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_email="test@example.com",
            email_verified=True,
            last_contacted_at=None,
            contact_count=0
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
    
    can_contact, last_contacted = await rate_limiter.check_cooldown(lead_id)
    
    assert can_contact, "Never contacted leads should be allowed"
    assert last_contacted is None, "Last contacted should be None"


@pytest.mark.asyncio
async def test_domain_throttle_enforcement(rate_limiter, test_db):
    """Test per-domain email throttling."""
    config = get_settings()
    limit = config.PER_DOMAIN_EMAIL_LIMIT
    domain = "example.com"
    
    # Create leads and send emails to same domain
    one_hour_ago = datetime.utcnow() - timedelta(minutes=30)
    
    with get_db_context() as db:
        for i in range(limit + 2):
            lead = Lead(
                source="google_maps",
                business_name=f"Business {i}",
                primary_email=f"user{i}@{domain}",
                email_verified=True
            )
            db.add(lead)
            db.flush()
            
            # Add email history
            if i < limit:
                history = OutreachHistory(
                    lead_id=lead.id,
                    outreach_type="email",
                    status="sent",
                    attempted_at=one_hour_ago + timedelta(minutes=i)
                )
                db.add(history)
        db.flush()
    
    # Check throttle for new email to same domain
    can_send, count = await rate_limiter.check_domain_throttle(f"newuser@{domain}")
    
    # Should be at or over limit
    assert count >= limit, f"Should have {limit} emails to domain"
    assert not can_send, "Should block when domain limit reached"


@pytest.mark.asyncio
async def test_get_eligible_leads_filters_correctly(rate_limiter, test_db):
    """Test that eligible leads query filters correctly."""
    with get_db_context() as db:
        # Create various leads
        # 1. Eligible lead
        eligible = Lead(
            source="google_maps",
            business_name="Eligible Business",
            primary_email="eligible@example.com",
            email_verified=True,
            opted_out=False,
            last_contacted_at=None
        )
        
        # 2. Opted out lead
        opted_out = Lead(
            source="google_maps",
            business_name="Opted Out Business",
            primary_email="optedout@example.com",
            email_verified=True,
            opted_out=True
        )
        
        # 3. Not verified lead
        not_verified = Lead(
            source="google_maps",
            business_name="Not Verified Business",
            primary_email="notverified@example.com",
            email_verified=False,
            opted_out=False
        )
        
        # 4. In cooldown lead
        in_cooldown = Lead(
            source="google_maps",
            business_name="Cooldown Business",
            primary_email="cooldown@example.com",
            email_verified=True,
            opted_out=False,
            last_contacted_at=datetime.utcnow() - timedelta(days=5)
        )
        
        db.add_all([eligible, opted_out, not_verified, in_cooldown])
        db.flush()
    
    # Get eligible leads
    eligible_leads = await rate_limiter.get_leads_eligible_for_outreach("email")
    
    # Should only return the eligible lead
    eligible_ids = [lead.id for lead in eligible_leads]
    assert eligible.id in eligible_ids, "Eligible lead should be included"
    assert opted_out.id not in eligible_ids, "Opted out lead should be excluded"
    assert not_verified.id not in eligible_ids, "Not verified lead should be excluded"
    assert in_cooldown.id not in eligible_ids, "Cooldown lead should be excluded"


@pytest.mark.asyncio
async def test_rate_limit_status(rate_limiter, test_db):
    """Test getting rate limit status."""
    status = await rate_limiter.get_rate_limit_status()
    
    assert "email" in status, "Should have email status"
    assert "call" in status, "Should have call status"
    assert "cooldown_days" in status, "Should have cooldown days"
    assert "per_domain_limit" in status, "Should have per-domain limit"
    
    # Email status
    assert "cap" in status["email"]
    assert "sent_today" in status["email"]
    assert "remaining" in status["email"]
    assert "can_send" in status["email"]
    
    # Call status
    assert "cap" in status["call"]
    assert "sent_today" in status["call"]
    assert "remaining" in status["call"]
    assert "can_send" in status["call"]


@pytest.mark.asyncio
async def test_enforce_caps_for_campaign(rate_limiter, test_db):
    """Test campaign cap enforcement."""
    # Email campaign
    can_proceed, remaining = await rate_limiter.enforce_caps_for_campaign("email")
    assert isinstance(can_proceed, bool), "Should return boolean"
    assert isinstance(remaining, int), "Should return integer"
    assert remaining >= 0, "Remaining should be non-negative"
    
    # Call campaign
    can_proceed, remaining = await rate_limiter.enforce_caps_for_campaign("call")
    assert isinstance(can_proceed, bool), "Should return boolean"
    assert isinstance(remaining, int), "Should return integer"
    assert remaining >= 0, "Remaining should be non-negative"


@pytest.mark.asyncio
async def test_increment_daily_counts(rate_limiter):
    """Test incrementing daily counts."""
    # Reset first
    await rate_limiter.reset_daily_counts()
    
    # Increment email count
    count1 = await rate_limiter.increment_daily_email_count()
    assert count1 == 1, "First increment should be 1"
    
    count2 = await rate_limiter.increment_daily_email_count()
    assert count2 == 2, "Second increment should be 2"
    
    # Increment call count
    call_count1 = await rate_limiter.increment_daily_call_count()
    assert call_count1 == 1, "First call increment should be 1"


@pytest.mark.asyncio
async def test_cooldown_with_nonexistent_lead(rate_limiter):
    """Test cooldown check with non-existent lead."""
    can_contact, last_contacted = await rate_limiter.check_cooldown(99999)
    
    assert not can_contact, "Should not allow contact for non-existent lead"
    assert last_contacted is None, "Last contacted should be None"


@pytest.mark.asyncio
async def test_domain_throttle_with_invalid_email(rate_limiter):
    """Test domain throttle with invalid email."""
    # Email without @ symbol
    can_send, count = await rate_limiter.check_domain_throttle("invalidemail")
    
    assert can_send, "Should allow invalid email (fail open)"
    assert count == 0, "Count should be 0 for invalid email"


@pytest.mark.asyncio
async def test_eligible_leads_limit(rate_limiter, test_db):
    """Test that eligible leads query respects limit."""
    # Create multiple eligible leads
    with get_db_context() as db:
        for i in range(10):
            lead = Lead(
                source="google_maps",
                business_name=f"Business {i}",
                primary_email=f"test{i}@example.com",
                email_verified=True,
                opted_out=False
            )
            db.add(lead)
        db.flush()
    
    # Get with limit
    eligible_leads = await rate_limiter.get_leads_eligible_for_outreach("email", limit=5)
    
    assert len(eligible_leads) <= 5, "Should respect limit parameter"


@pytest.mark.asyncio
async def test_eligible_leads_prioritizes_never_contacted(rate_limiter, test_db):
    """Test that never contacted leads are prioritized."""
    with get_db_context() as db:
        # Create never contacted lead
        never_contacted = Lead(
            source="google_maps",
            business_name="Never Contacted",
            primary_email="never@example.com",
            email_verified=True,
            opted_out=False,
            last_contacted_at=None
        )
        
        # Create previously contacted lead (outside cooldown)
        previously_contacted = Lead(
            source="google_maps",
            business_name="Previously Contacted",
            primary_email="previous@example.com",
            email_verified=True,
            opted_out=False,
            last_contacted_at=datetime.utcnow() - timedelta(days=60)
        )
        
        db.add(previously_contacted)
        db.add(never_contacted)
        db.flush()
        never_id = never_contacted.id
        previous_id = previously_contacted.id
    
    # Get eligible leads
    eligible_leads = await rate_limiter.get_leads_eligible_for_outreach("email", limit=10)
    
    # Never contacted should come first
    if len(eligible_leads) >= 2:
        # Find positions
        never_pos = next((i for i, lead in enumerate(eligible_leads) if lead.id == never_id), None)
        previous_pos = next((i for i, lead in enumerate(eligible_leads) if lead.id == previous_id), None)
        
        if never_pos is not None and previous_pos is not None:
            assert never_pos < previous_pos, "Never contacted leads should be prioritized"
