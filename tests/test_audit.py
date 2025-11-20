"""Property-based tests for audit logging system.

Feature: devsync-sales-ai
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
import re
from datetime import datetime

from app.audit import AuditLogger, get_audit_logger


# Property 56: Sensitive data masking
@pytest.mark.property
@given(
    api_key=st.text(min_size=16, max_size=64, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    key_name=st.sampled_from([
        "api_key", "API_KEY", "auth_token", "AUTH-TOKEN",
        "password", "PASSWORD", "secret", "SECRET",
        "sendgrid_api_key", "twilio_auth_token", "openai_api_key"
    ])
)
@settings(max_examples=100)
def test_property_56_sensitive_data_masking(api_key, key_name):
    """
    Feature: devsync-sales-ai, Property 56: Sensitive data masking
    For any log entry that would contain sensitive configuration values (API keys, passwords),
    the system must mask or redact the values before logging.
    
    Validates: Requirements 17.4
    """
    audit = AuditLogger()
    
    # Create data with sensitive field
    data = {
        key_name: api_key,
        "other_field": "normal_value"
    }
    
    # Mask the data
    masked = audit._mask_sensitive_data(data)
    
    # Verify sensitive field is masked
    assert key_name in masked
    assert masked[key_name] != api_key, "Sensitive value must be masked"
    
    # Verify masking format
    if len(api_key) > 8:
        # Should show first 4 and last 4 characters
        assert api_key[:4] in masked[key_name]
        assert api_key[-4:] in masked[key_name]
        assert "..." in masked[key_name]
    else:
        # Short values should be completely masked
        assert masked[key_name] == "****"
    
    # Verify non-sensitive field is not masked
    assert masked["other_field"] == "normal_value"


@pytest.mark.property
@given(
    email=st.emails(),
    phone=st.from_regex(r"\+91[6-9]\d{9}", fullmatch=True)
)
@settings(max_examples=100)
def test_property_56_pii_masking(email, phone):
    """
    Feature: devsync-sales-ai, Property 56: Sensitive data masking
    Test that PII (emails, phone numbers) are masked in log strings.
    
    Validates: Requirements 17.4
    """
    audit = AuditLogger()
    
    # Create text with PII
    text = f"Sending email to {email} and calling {phone}"
    
    # Mask the text
    masked = audit._mask_string(text)
    
    # Verify email is masked (should not contain full email)
    assert email not in masked, "Full email must be masked"
    
    # Verify phone is masked (should not contain full phone)
    assert phone not in masked, "Full phone must be masked"
    
    # Verify some parts are still visible (for debugging)
    # Email should show first 2 chars and domain
    email_parts = email.split('@')
    if len(email_parts[0]) >= 2:
        assert email_parts[0][:2] in masked
    assert email_parts[1] in masked  # Domain should be visible
    
    # Phone should show last 4 digits
    assert phone[-4:] in masked


@pytest.mark.property
@given(
    nested_data=st.dictionaries(
        keys=st.sampled_from(["api_key", "normal_field", "password", "data"]),
        values=st.one_of(
            st.text(min_size=1, max_size=50),
            st.integers(),
            st.booleans(),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.text(min_size=1, max_size=50)
            )
        ),
        min_size=1,
        max_size=5
    )
)
@settings(max_examples=50)
def test_property_56_nested_masking(nested_data):
    """
    Feature: devsync-sales-ai, Property 56: Sensitive data masking
    Test that sensitive data is masked even in nested structures.
    
    Validates: Requirements 17.4
    """
    audit = AuditLogger()
    
    # Mask nested data
    masked = audit._mask_sensitive_data(nested_data)
    
    # Verify structure is preserved
    assert isinstance(masked, dict)
    assert set(masked.keys()) == set(nested_data.keys())
    
    # Verify sensitive keys are masked
    for key, value in nested_data.items():
        if any(pattern in key.lower() for pattern in ["api_key", "password", "secret", "token"]):
            if isinstance(value, str) and len(value) > 0:
                # Sensitive value should be masked
                assert masked[key] != value or value == "****"


@pytest.mark.property
@given(
    data_list=st.lists(
        st.dictionaries(
            keys=st.sampled_from(["api_key", "email", "normal"]),
            values=st.text(min_size=1, max_size=30)
        ),
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=50)
def test_property_56_list_masking(data_list):
    """
    Feature: devsync-sales-ai, Property 56: Sensitive data masking
    Test that sensitive data is masked in lists of dictionaries.
    
    Validates: Requirements 17.4
    """
    audit = AuditLogger()
    
    # Mask list data
    masked = audit._mask_sensitive_data(data_list)
    
    # Verify structure is preserved
    assert isinstance(masked, list)
    assert len(masked) == len(data_list)
    
    # Verify each item is masked appropriately
    for original, masked_item in zip(data_list, masked):
        assert isinstance(masked_item, dict)
        if "api_key" in original:
            # API key should be masked
            assert masked_item["api_key"] != original["api_key"] or original["api_key"] == "****"


# Unit tests for specific audit logging scenarios
@pytest.mark.asyncio
async def test_log_outreach():
    """Test logging outreach attempts."""
    audit = get_audit_logger()
    
    result = {
        "status": "sent",
        "provider": "sendgrid",
        "message_id": "msg_123",
        "api_key": "SG.1234567890abcdefghij"  # Should be masked
    }
    
    # Log outreach (should not raise exception)
    await audit.log_outreach(
        lead_id=1,
        outreach_type="email",
        result=result
    )
    
    # Verify masking happened (check internal state)
    masked = audit._mask_sensitive_data(result)
    assert masked["api_key"] != result["api_key"]


@pytest.mark.asyncio
async def test_log_opt_out():
    """Test logging opt-out requests."""
    audit = get_audit_logger()
    
    # Log opt-out (should not raise exception)
    await audit.log_opt_out(
        contact="test@example.com",
        method="link",
        lead_id=1
    )


@pytest.mark.asyncio
async def test_log_api_call():
    """Test logging API calls."""
    audit = get_audit_logger()
    
    result = {
        "status_code": 200,
        "response": {"success": True},
        "auth_token": "Bearer abc123xyz"  # Should be masked
    }
    
    await audit.log_api_call(
        service="twilio",
        endpoint="calls",
        result=result,
        lead_id=1
    )
    
    # Verify masking
    masked = audit._mask_sensitive_data(result)
    assert masked["auth_token"] != result["auth_token"]


@pytest.mark.asyncio
async def test_log_error():
    """Test logging errors."""
    audit = get_audit_logger()
    
    try:
        raise ValueError("Test error")
    except ValueError as e:
        await audit.log_error(
            component="test",
            error=e,
            context={"operation": "test_operation"},
            lead_id=1
        )


@pytest.mark.asyncio
async def test_log_verification():
    """Test logging verification attempts."""
    audit = get_audit_logger()
    
    result = {
        "is_valid": True,
        "confidence": 0.95,
        "provider": "AbstractAPI",
        "api_key": "abc123"  # Should be masked
    }
    
    await audit.log_verification(
        lead_id=1,
        verification_type="email",
        result=result
    )
    
    # Verify masking
    masked = audit._mask_sensitive_data(result)
    assert masked["api_key"] == "****"  # Short key fully masked


@pytest.mark.asyncio
async def test_log_campaign():
    """Test logging campaign events."""
    audit = get_audit_logger()
    
    details = {
        "total_attempted": 100,
        "total_success": 95,
        "total_failed": 5
    }
    
    await audit.log_campaign(
        campaign_id=1,
        campaign_type="email",
        action="complete",
        details=details
    )


@pytest.mark.asyncio
async def test_log_approval():
    """Test logging approval actions."""
    audit = get_audit_logger()
    
    await audit.log_approval(
        approval_id=1,
        action="approve",
        user_id="operator_123",
        lead_id=1
    )


def test_email_masking_patterns():
    """Test various email masking patterns."""
    audit = AuditLogger()
    
    test_cases = [
        ("test@example.com", "te***@example.com"),
        ("a@b.com", "a***@b.com"),
        ("very.long.email@domain.co.uk", "ve***@domain.co.uk"),
    ]
    
    for original, expected_pattern in test_cases:
        masked = audit._mask_string(f"Email: {original}")
        assert original not in masked
        # Check that domain is preserved
        domain = original.split('@')[1]
        assert domain in masked


def test_phone_masking_patterns():
    """Test various phone masking patterns."""
    audit = AuditLogger()
    
    test_cases = [
        "+919876543210",
        "+1234567890",
        "9876543210"
    ]
    
    for phone in test_cases:
        masked = audit._mask_string(f"Phone: {phone}")
        assert phone not in masked
        # Check that last 4 digits are preserved
        if len(phone) >= 4:
            assert phone[-4:] in masked


def test_nested_dict_masking():
    """Test masking in deeply nested dictionaries."""
    audit = AuditLogger()
    
    data = {
        "level1": {
            "api_key": "secret123456",
            "level2": {
                "password": "pass123456",
                "normal": "value"
            }
        },
        "other": "data"
    }
    
    masked = audit._mask_sensitive_data(data)
    
    # Verify structure preserved
    assert "level1" in masked
    assert "level2" in masked["level1"]
    
    # Verify sensitive data masked
    assert masked["level1"]["api_key"] != "secret123456"
    assert masked["level1"]["level2"]["password"] != "pass123456"
    
    # Verify normal data not masked
    assert masked["level1"]["level2"]["normal"] == "value"
    assert masked["other"] == "data"


def test_format_log_entry():
    """Test log entry formatting."""
    audit = AuditLogger()
    
    entry = audit._format_log_entry(
        log_level="INFO",
        component="test",
        action="test_action",
        details={"key": "value", "api_key": "secret"},
        lead_id=1,
        user_id="user_123"
    )
    
    # Verify structure
    assert "timestamp" in entry
    assert entry["log_level"] == "INFO"
    assert entry["component"] == "test"
    assert entry["action"] == "test_action"
    assert entry["lead_id"] == 1
    assert entry["user_id"] == "user_123"
    
    # Verify masking in details
    assert entry["details"]["key"] == "value"
    assert entry["details"]["api_key"] != "secret"


def test_multiple_sensitive_patterns():
    """Test that multiple sensitive patterns are all masked."""
    audit = AuditLogger()
    
    data = {
        "api_key": "key123456789",
        "auth_token": "token123456789",
        "password": "pass123456789",
        "secret": "secret123456789",
        "normal_field": "normal_value"
    }
    
    masked = audit._mask_sensitive_data(data)
    
    # All sensitive fields should be masked
    for key in ["api_key", "auth_token", "password", "secret"]:
        assert masked[key] != data[key]
        assert "..." in masked[key]
    
    # Normal field should not be masked
    assert masked["normal_field"] == "normal_value"
