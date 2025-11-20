"""Property-based tests for email outreach service."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from hypothesis import given, strategies as st, settings
import uuid

from app.outreach.emailer import EmailSender, OutreachEmail, SendResult
from app.models import Lead, OptOut, OutreachHistory
from app.db import get_db_context
from app.config import get_settings


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def email_sender():
    """Create email sender instance."""
    return EmailSender()


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
def email_address(draw):
    """Generate valid email addresses."""
    username = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd')),
        min_size=3,
        max_size=20
    ))
    domain = draw(st.sampled_from([
        "business.com", "company.org", "enterprise.net",
        "shop.in", "services.co"
    ]))
    return f"{username}@{domain}"


@st.composite
def outreach_email_strategy(draw, lead_id=1):
    """Generate outreach email data."""
    return OutreachEmail(
        lead_id=lead_id,
        to_email=draw(email_address()),
        subject=draw(st.text(min_size=10, max_size=100)),
        body_html=draw(st.text(min_size=50, max_size=500)),
        body_text=draw(st.text(min_size=50, max_size=500)),
        unsubscribe_token=str(uuid.uuid4())
    )


# ============================================================================
# Property Tests
# ============================================================================

@settings(max_examples=100)
@given(email=outreach_email_strategy())
@pytest.mark.asyncio
async def test_property_10_unsubscribe_link_presence(email, email_sender):
    """
    Feature: devsync-sales-ai, Property 10: Unsubscribe link presence
    For any generated outreach email, the email body must contain an
    unsubscribe link with a unique token.
    Validates: Requirements 3.1
    """
    # Add compliance footer
    body_html, body_text = email_sender.add_compliance_footer(
        email.body_html,
        email.body_text,
        email.unsubscribe_token
    )
    
    # Check HTML body contains unsubscribe
    assert "unsubscribe" in body_html.lower(), "HTML body must contain unsubscribe link"
    assert email.unsubscribe_token in body_html, "HTML body must contain unique token"
    
    # Check text body contains unsubscribe
    assert "unsubscribe" in body_text.lower(), "Text body must contain unsubscribe link"
    assert email.unsubscribe_token in body_text, "Text body must contain unique token"
    
    # Verify token is UUID format (at least 32 chars)
    assert len(email.unsubscribe_token) >= 32, "Token must be at least 32 characters"


@settings(max_examples=100)
@given(email=outreach_email_strategy())
@pytest.mark.asyncio
async def test_property_22_email_compliance_elements(email, email_sender):
    """
    Feature: devsync-sales-ai, Property 22: Email compliance elements
    For any generated outreach email, the email must include sender's physical
    address, business identity (DevSync Innovation), and an unsubscribe link.
    Validates: Requirements 6.1
    """
    config = get_settings()
    
    # Add compliance footer
    body_html, body_text = email_sender.add_compliance_footer(
        email.body_html,
        email.body_text,
        email.unsubscribe_token
    )
    
    # Check business identity
    assert config.EMAIL_FROM_NAME in body_html, "Must include business name in HTML"
    assert config.EMAIL_FROM_NAME in body_text, "Must include business name in text"
    
    # Check physical address
    assert config.BUSINESS_ADDRESS in body_html, "Must include physical address in HTML"
    assert config.BUSINESS_ADDRESS in body_text, "Must include physical address in text"
    
    # Check unsubscribe link
    assert "unsubscribe" in body_html.lower(), "Must include unsubscribe link in HTML"
    assert "unsubscribe" in body_text.lower(), "Must include unsubscribe link in text"


@settings(max_examples=100)
@given(
    original_html=st.text(min_size=50, max_size=200),
    original_text=st.text(min_size=50, max_size=200)
)
@pytest.mark.asyncio
async def test_property_31_compliance_footer_appending(original_html, original_text, email_sender):
    """
    Feature: devsync-sales-ai, Property 31: Compliance footer appending
    For any finalized email content, the system must append compliance elements
    (address, identity, unsubscribe link) to the email body.
    Validates: Requirements 9.4
    """
    token = str(uuid.uuid4())
    
    # Add compliance footer
    final_html, final_text = email_sender.add_compliance_footer(
        original_html,
        original_text,
        token
    )
    
    # Verify original content is preserved
    assert original_html in final_html, "Original HTML content must be preserved"
    assert original_text in final_text, "Original text content must be preserved"
    
    # Verify footer is appended (content is longer)
    assert len(final_html) > len(original_html), "HTML must be longer after footer"
    assert len(final_text) > len(original_text), "Text must be longer after footer"
    
    # Verify compliance elements are present
    config = get_settings()
    assert config.BUSINESS_ADDRESS in final_html, "Footer must include address"
    assert token in final_html, "Footer must include unsubscribe token"


@settings(max_examples=100)
@given(email=outreach_email_strategy())
@pytest.mark.asyncio
async def test_property_32_pre_send_persistence(email, email_sender, test_db):
    """
    Feature: devsync-sales-ai, Property 32: Pre-send persistence
    For any email ready to send, the system must persist the complete email
    content to the database before transmission.
    Validates: Requirements 9.5
    """
    # Create a test lead
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_email=email.to_email,
            email_verified=True
        )
        db.add(lead)
        db.flush()
        email.lead_id = lead.id
    
    # Calculate content hash
    content_hash = email_sender.calculate_content_hash(email.subject, email.body_text)
    
    # Persist before send
    history_id = await email_sender.persist_before_send(email, content_hash)
    
    # Verify record was created
    assert history_id is not None, "History ID must be returned"
    assert history_id > 0, "History ID must be positive"
    
    # Verify record exists in database
    with get_db_context() as db:
        history = db.query(OutreachHistory).filter(OutreachHistory.id == history_id).first()
        assert history is not None, "History record must exist"
        assert history.lead_id == email.lead_id, "Lead ID must match"
        assert history.outreach_type == "email", "Type must be email"
        assert history.content_hash == content_hash, "Content hash must match"
        assert history.status == "pending", "Initial status must be pending"


@settings(max_examples=50)
@given(provider=st.sampled_from(["sendgrid", "mailgun", "smtp"]))
@pytest.mark.asyncio
async def test_property_33_provider_usage(provider, email_sender):
    """
    Feature: devsync-sales-ai, Property 33: Provider usage
    For any email sent, the system must use the configured email provider
    (SendGrid, Mailgun, or SMTP) with proper authentication.
    Validates: Requirements 10.1
    """
    # Mock the provider methods
    with patch.object(email_sender, '_send_via_sendgrid', new_callable=AsyncMock) as mock_sg, \
         patch.object(email_sender, '_send_via_mailgun', new_callable=AsyncMock) as mock_mg, \
         patch.object(email_sender, '_send_via_smtp', new_callable=AsyncMock) as mock_smtp:
        
        # Set return values
        mock_sg.return_value = SendResult(success=True, message_id="test-id")
        mock_mg.return_value = SendResult(success=True, message_id="test-id")
        mock_smtp.return_value = SendResult(success=True, message_id="test-id")
        
        # Set provider
        email_sender.provider = provider
        
        # Create test email
        email = OutreachEmail(
            lead_id=1,
            to_email="test@example.com",
            subject="Test",
            body_html="<p>Test</p>",
            body_text="Test",
            unsubscribe_token=str(uuid.uuid4())
        )
        
        # Send with retry
        result = await email_sender._send_with_retry(email, email.body_html, email.body_text)
        
        # Verify correct provider was called
        if provider == "sendgrid":
            mock_sg.assert_called_once()
            mock_mg.assert_not_called()
            mock_smtp.assert_not_called()
        elif provider == "mailgun":
            mock_mg.assert_called_once()
            mock_sg.assert_not_called()
            mock_smtp.assert_not_called()
        elif provider == "smtp":
            mock_smtp.assert_called_once()
            mock_sg.assert_not_called()
            mock_mg.assert_not_called()


@settings(max_examples=100)
@given(attempt=st.integers(min_value=0, max_value=5))
@pytest.mark.asyncio
async def test_property_34_transient_error_retry(attempt, email_sender):
    """
    Feature: devsync-sales-ai, Property 34: Transient error retry
    For any email send that fails with a transient error (rate limit, timeout),
    the system must retry using exponential backoff with a maximum of 3 attempts.
    Validates: Requirements 10.2
    """
    # Mock provider to fail with transient error
    with patch.object(email_sender, '_send_via_sendgrid', new_callable=AsyncMock) as mock_send:
        # Simulate transient error
        mock_send.return_value = SendResult(
            success=False,
            error="Rate limit exceeded (429)"
        )
        
        email_sender.provider = "sendgrid"
        
        email = OutreachEmail(
            lead_id=1,
            to_email="test@example.com",
            subject="Test",
            body_html="<p>Test</p>",
            body_text="Test",
            unsubscribe_token=str(uuid.uuid4())
        )
        
        # Send with retry
        result = await email_sender._send_with_retry(email, email.body_html, email.body_text, max_retries=3)
        
        # Verify retries occurred (should be called 3 times)
        assert mock_send.call_count == 3, "Should retry 3 times for transient errors"
        assert not result.success, "Should fail after exhausting retries"


@settings(max_examples=100)
@given(error_msg=st.sampled_from([
    "Invalid recipient",
    "Email does not exist",
    "Blocked domain",
    "401 Unauthorized",
    "403 Forbidden"
]))
@pytest.mark.asyncio
async def test_property_35_permanent_error_handling(error_msg, email_sender):
    """
    Feature: devsync-sales-ai, Property 35: Permanent error handling
    For any email send that fails with a permanent error (invalid recipient, blocked),
    the system must mark the lead as undeliverable and exclude it from future campaigns.
    Validates: Requirements 10.3
    """
    # Check if error is classified as permanent
    is_permanent = email_sender._is_permanent_error(error_msg)
    
    # All these errors should be classified as permanent
    assert is_permanent, f"Error '{error_msg}' should be classified as permanent"
    
    # Mock provider to return permanent error
    with patch.object(email_sender, '_send_via_sendgrid', new_callable=AsyncMock) as mock_send:
        mock_send.return_value = SendResult(success=False, error=error_msg)
        
        email_sender.provider = "sendgrid"
        
        email = OutreachEmail(
            lead_id=1,
            to_email="test@example.com",
            subject="Test",
            body_html="<p>Test</p>",
            body_text="Test",
            unsubscribe_token=str(uuid.uuid4())
        )
        
        # Send with retry
        result = await email_sender._send_with_retry(email, email.body_html, email.body_text, max_retries=3)
        
        # Should not retry on permanent errors
        assert mock_send.call_count == 1, "Should not retry on permanent errors"
        assert not result.success, "Should fail immediately"


@settings(max_examples=100)
@given(
    event_type=st.sampled_from(["bounce", "complaint", "unsubscribe", "delivered"]),
    email_addr=email_address()
)
@pytest.mark.asyncio
async def test_property_36_webhook_processing(event_type, email_addr, email_sender, test_db):
    """
    Feature: devsync-sales-ai, Property 36: Webhook processing
    For any webhook notification received from the email provider, the system
    must process the event and update the corresponding lead status in the database.
    Validates: Requirements 10.4
    """
    # Create test lead
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_email=email_addr,
            email_verified=True
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
    
    # Create webhook event
    event = {
        "event": event_type,
        "email": email_addr,
        "message_id": "test-msg-123",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Process webhook
    await email_sender.handle_webhook(event)
    
    # Verify appropriate action was taken
    with get_db_context() as db:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        
        if event_type in ["bounce", "complaint", "unsubscribe"]:
            # Check if opt-out was created
            opt_out = db.query(OptOut).filter(
                OptOut.contact_type == "email",
                OptOut.contact_value == email_addr
            ).first()
            
            if event_type == "unsubscribe" or event_type == "complaint":
                assert opt_out is not None, f"Opt-out should be created for {event_type}"
                assert lead.opted_out, "Lead should be marked as opted out"


@settings(max_examples=100)
@given(
    domain=st.sampled_from(["example.com", "business.org", "company.net"]),
    email_count=st.integers(min_value=1, max_value=10)
)
@pytest.mark.asyncio
async def test_property_16_per_domain_throttling(domain, email_count, email_sender):
    """
    Feature: devsync-sales-ai, Property 16: Per-domain throttling
    For any domain, the number of emails sent to that domain within a 1-hour
    window must not exceed 5.
    Validates: Requirements 4.3
    """
    config = get_settings()
    limit = config.PER_DOMAIN_EMAIL_LIMIT
    
    # Reset throttle
    email_sender._domain_throttle = {}
    
    # Try to send emails to the domain
    allowed_count = 0
    for i in range(email_count):
        email_addr = f"user{i}@{domain}"
        can_send = await email_sender.check_domain_throttle(email_addr)
        
        if can_send:
            email_sender.record_domain_send(email_addr)
            allowed_count += 1
    
    # Verify throttle limit is enforced
    assert allowed_count <= limit, f"Should not allow more than {limit} emails per domain per hour"
    
    # If we tried to send more than the limit, verify some were blocked
    if email_count > limit:
        assert allowed_count == limit, f"Should allow exactly {limit} emails when limit is exceeded"


# ============================================================================
# Unit Tests for Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_opted_out_email_blocked(email_sender, test_db):
    """Test that opted-out emails are blocked."""
    email_addr = "optedout@example.com"
    
    # Create opt-out record
    with get_db_context() as db:
        opt_out = OptOut(
            contact_type="email",
            contact_value=email_addr,
            opt_out_method="link",
            opted_out_at=datetime.utcnow()
        )
        db.add(opt_out)
    
    # Try to send email
    email = OutreachEmail(
        lead_id=1,
        to_email=email_addr,
        subject="Test",
        body_html="<p>Test</p>",
        body_text="Test",
        unsubscribe_token=str(uuid.uuid4())
    )
    
    result = await email_sender.send(email)
    
    # Should be blocked
    assert not result.success
    assert "opted out" in result.error.lower()


@pytest.mark.asyncio
async def test_dry_run_mode_no_actual_send(email_sender, test_db):
    """Test that dry-run mode doesn't actually send emails."""
    config = get_settings()
    original_dry_run = config.DRY_RUN_MODE
    
    try:
        # Enable dry-run mode
        config.DRY_RUN_MODE = True
        
        email = OutreachEmail(
            lead_id=1,
            to_email="test@example.com",
            subject="Test",
            body_html="<p>Test</p>",
            body_text="Test",
            unsubscribe_token=str(uuid.uuid4())
        )
        
        with patch.object(email_sender, '_send_via_sendgrid', new_callable=AsyncMock) as mock_send:
            result = await email_sender.send(email)
            
            # Should succeed but not actually call provider
            assert result.success
            assert "dry-run" in result.message_id
            mock_send.assert_not_called()
    
    finally:
        config.DRY_RUN_MODE = original_dry_run


@pytest.mark.asyncio
async def test_content_hash_calculation(email_sender):
    """Test content hash is calculated correctly."""
    subject = "Test Subject"
    body = "Test Body Content"
    
    hash1 = email_sender.calculate_content_hash(subject, body)
    hash2 = email_sender.calculate_content_hash(subject, body)
    
    # Same content should produce same hash
    assert hash1 == hash2
    
    # Different content should produce different hash
    hash3 = email_sender.calculate_content_hash(subject, "Different Body")
    assert hash1 != hash3
    
    # Hash should be 64 characters (SHA256 hex)
    assert len(hash1) == 64


@pytest.mark.asyncio
async def test_exponential_backoff_calculation(email_sender):
    """Test exponential backoff delays increase correctly."""
    delay0 = email_sender._calculate_backoff(0)
    delay1 = email_sender._calculate_backoff(1)
    delay2 = email_sender._calculate_backoff(2)
    
    # Delays should increase exponentially
    assert delay0 < delay1 < delay2
    
    # First delay should be around 1 second
    assert 1.0 <= delay0 <= 2.0
    
    # Second delay should be around 4 seconds
    assert 4.0 <= delay1 <= 5.0
    
    # Third delay should be around 16 seconds
    assert 16.0 <= delay2 <= 17.0
