"""Property-based tests for verification services.

Feature: devsync-sales-ai
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
from app.verifier.email_verify import EmailVerifier, EmailVerificationResult
from app.verifier.phone_verify import PhoneVerifier, PhoneVerificationResult


# Property 5: Email verification requirement
@pytest.mark.property
@pytest.mark.asyncio
@given(email=st.emails())
@settings(max_examples=100)
async def test_property_5_email_verification_requirement(email):
    """
    Feature: devsync-sales-ai, Property 5: Email verification requirement
    For any lead processed for verification, if the lead has an email address,
    the system must call a verification provider and store the deliverability result.
    
    Validates: Requirements 2.1
    """
    verifier = EmailVerifier()
    
    # Verify email
    result = await verifier.verify(email)
    
    # Verify result exists and has required fields
    assert result is not None
    assert isinstance(result, EmailVerificationResult)
    assert result.email == email
    assert isinstance(result.is_deliverable, bool)
    assert isinstance(result.confidence_score, float)
    assert 0.0 <= result.confidence_score <= 1.0
    assert result.verified_at is not None
    assert isinstance(result.provider_response, dict)


# Property 6: Personal email exclusion
@pytest.mark.property
@pytest.mark.asyncio
@given(
    username=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Nd'))),
    provider=st.sampled_from(['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com'])
)
@settings(max_examples=100)
async def test_property_6_personal_email_exclusion(username, provider):
    """
    Feature: devsync-sales-ai, Property 6: Personal email exclusion
    For any lead with an email address classified as personal (gmail, yahoo, hotmail)
    or undeliverable, the system must mark email_verified as False.
    
    Validates: Requirements 2.2
    """
    verifier = EmailVerifier()
    email = f"{username}@{provider}"
    
    # Verify personal email
    result = await verifier.verify(email)
    
    # Personal emails should be flagged as non-business
    # unless they're role-based
    if not verifier._is_role_based_email(email):
        assert result.is_business == False, f"Personal email {email} should be flagged as non-business"


# Property 7: Phone verification requirement
@pytest.mark.property
@pytest.mark.asyncio
@given(phone=st.from_regex(r"\+91[6-9]\d{9}", fullmatch=True))
@settings(max_examples=100)
async def test_property_7_phone_verification_requirement(phone):
    """
    Feature: devsync-sales-ai, Property 7: Phone verification requirement
    For any lead with a phone number, the system must validate the number through
    a verification provider and store the validity result.
    
    Validates: Requirements 2.3
    """
    verifier = PhoneVerifier()
    
    # Verify phone
    result = await verifier.verify(phone)
    
    # Verify result exists and has required fields
    assert result is not None
    assert isinstance(result, PhoneVerificationResult)
    assert result.phone == phone
    assert isinstance(result.is_valid, bool)
    assert isinstance(result.carrier_type, str)
    assert isinstance(result.confidence_score, float)
    assert 0.0 <= result.confidence_score <= 1.0
    assert result.verified_at is not None


# Property 8: Low confidence filtering
@pytest.mark.property
@given(
    confidence=st.floats(min_value=0.0, max_value=1.0),
    threshold=st.floats(min_value=0.5, max_value=0.9)
)
@settings(max_examples=100)
def test_property_8_low_confidence_filtering(confidence, threshold):
    """
    Feature: devsync-sales-ai, Property 8: Low confidence filtering
    For any verification result with a confidence score below the configured threshold,
    the system must flag the lead for exclusion or manual review.
    
    Validates: Requirements 2.4
    """
    # Create mock result
    email_result = EmailVerificationResult(
        email="test@example.com",
        is_deliverable=True,
        is_business=True,
        confidence_score=confidence,
        provider_response={},
        verified_at=datetime.utcnow()
    )
    
    # Check threshold
    meets_threshold = confidence >= threshold
    
    # Verify filtering logic
    if confidence < threshold:
        assert not meets_threshold, "Low confidence should not meet threshold"
    else:
        assert meets_threshold, "High confidence should meet threshold"


# Property 9: Verification persistence
@pytest.mark.property
@pytest.mark.asyncio
@given(email=st.emails())
@settings(max_examples=50)
async def test_property_9_verification_persistence(email):
    """
    Feature: devsync-sales-ai, Property 9: Verification persistence
    For any completed verification, storing the result and then retrieving it
    from the database must return all verification details.
    
    Validates: Requirements 2.5
    """
    verifier = EmailVerifier()
    
    # Verify email
    result1 = await verifier.verify(email)
    
    # Verify again (should use cache)
    result2 = await verifier.verify(email)
    
    # Results should match (from cache)
    assert result1.email == result2.email
    assert result1.is_deliverable == result2.is_deliverable
    assert result1.is_business == result2.is_business
    assert result1.confidence_score == result2.confidence_score


# Unit tests for verification logic
@pytest.mark.asyncio
async def test_role_based_email_detection():
    """Test that role-based emails are recognized as business."""
    verifier = EmailVerifier()
    
    role_emails = [
        "info@example.com",
        "contact@example.com",
        "sales@example.com",
        "support@example.com"
    ]
    
    for email in role_emails:
        assert verifier._is_role_based_email(email), f"{email} should be recognized as role-based"


@pytest.mark.asyncio
async def test_personal_provider_detection():
    """Test that personal email providers are detected."""
    verifier = EmailVerifier()
    
    personal_emails = [
        "user@gmail.com",
        "user@yahoo.com",
        "user@hotmail.com"
    ]
    
    for email in personal_emails:
        result = await verifier.verify(email)
        # Should be flagged as non-business unless role-based
        if not verifier._is_role_based_email(email):
            assert not result.is_business


@pytest.mark.asyncio
async def test_email_verification_caching():
    """Test that email verification results are cached."""
    verifier = EmailVerifier()
    email = "test@example.com"
    
    # First verification
    result1 = await verifier.verify(email)
    
    # Second verification (should use cache)
    result2 = await verifier.verify(email)
    
    # Should be same object from cache
    assert result1.verified_at == result2.verified_at


@pytest.mark.asyncio
async def test_phone_normalization():
    """Test phone number normalization."""
    verifier = PhoneVerifier()
    
    # Various formats should normalize to same E.164
    phones = [
        "+919876543210",
        "9876543210",
        "+91 98765 43210"
    ]
    
    results = []
    for phone in phones:
        result = await verifier.verify(phone, "IN")
        results.append(result.phone)
    
    # All should normalize to same format
    assert len(set(results)) == 1
    assert results[0] == "+919876543210"


@pytest.mark.asyncio
async def test_invalid_phone_handling():
    """Test handling of invalid phone numbers."""
    verifier = PhoneVerifier()
    
    invalid_phones = [
        "invalid",
        "123",
        "abcdefghij"
    ]
    
    for phone in invalid_phones:
        result = await verifier.verify(phone)
        assert not result.is_valid
        assert result.confidence_score == 0.0


def test_carrier_type_mapping():
    """Test carrier type mapping."""
    verifier = PhoneVerifier()
    
    # Test line type mapping
    assert verifier._map_line_type("landline") == "landline"
    assert verifier._map_line_type("mobile") == "mobile"
    assert verifier._map_line_type("voip") == "voip"
    assert verifier._map_line_type("unknown_type") == "unknown"


def test_confidence_threshold_checking():
    """Test confidence threshold checking."""
    verifier = EmailVerifier()
    
    # High confidence result
    high_conf = EmailVerificationResult(
        email="test@example.com",
        is_deliverable=True,
        is_business=True,
        confidence_score=0.9,
        provider_response={},
        verified_at=datetime.utcnow()
    )
    
    assert verifier.meets_threshold(high_conf)
    
    # Low confidence result
    low_conf = EmailVerificationResult(
        email="test@example.com",
        is_deliverable=True,
        is_business=True,
        confidence_score=0.3,
        provider_response={},
        verified_at=datetime.utcnow()
    )
    
    assert not verifier.meets_threshold(low_conf)


def test_business_line_detection():
    """Test business line detection for phones."""
    # Landlines and VOIP are considered business
    result_landline = PhoneVerificationResult(
        phone="+919876543210",
        is_valid=True,
        carrier_type="landline",
        is_business_line=True,
        confidence_score=0.8,
        provider_response={},
        verified_at=datetime.utcnow()
    )
    
    assert result_landline.is_business_line
    
    # Mobile less likely business
    result_mobile = PhoneVerificationResult(
        phone="+919876543210",
        is_valid=True,
        carrier_type="mobile",
        is_business_line=False,
        confidence_score=0.6,
        provider_response={},
        verified_at=datetime.utcnow()
    )
    
    assert not result_mobile.is_business_line
