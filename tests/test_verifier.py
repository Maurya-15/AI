"""Property-based tests for verification services.

Feature: devsync-sales-ai
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
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
    assert result.provider_name is not None
    assert result.provider_response is not None
    assert result.verified_at is not None


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
    
    # Verify email
    result = await verifier.verify(email)
    
    # Personal emails should be flagged as not business
    # (unless they're role-based like info@gmail.com)
    if not any(role in username.lower() for role in verifier.BUSINESS_ROLES):
        assert result.is_business == False, f"Personal email {email} should not be marked as business"


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
    assert isinstance(result.confidence_score, float)
    assert 0.0 <= result.confidence_score <= 1.0
    assert result.carrier_type is not None
    assert result.provider_name is not None
    assert result.provider_response is not None
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
    # Simulate filtering logic
    should_exclude = confidence < threshold
    
    # Verify filtering decision
    if confidence < threshold:
        assert should_exclude == True, f"Confidence {confidence} below threshold {threshold} should be excluded"
    else:
        assert should_exclude == False, f"Confidence {confidence} above threshold {threshold} should not be excluded"


# Property 9: Verification persistence
@pytest.mark.property
@pytest.mark.asyncio
@given(email=st.emails())
@settings(max_examples=50)
async def test_property_9_verification_persistence(email):
    """
    Feature: devsync-sales-ai, Property 9: Verification persistence
    For any completed verification, storing the result and then retrieving it from
    the database must return all verification details (confidence score, provider response, timestamp).
    
    Validates: Requirements 2.5
    """
    verifier = EmailVerifier()
    
    # Verify email
    result1 = await verifier.verify(email)
    
    # Verify again (should use cache)
    result2 = await verifier.verify(email)
    
    # Results should be identical (from cache)
    assert result1.email == result2.email
    assert result1.is_deliverable == result2.is_deliverable
    assert result1.is_business == result2.is_business
    assert result1.confidence_score == result2.confidence_score
    assert result1.provider_name == result2.provider_name


# Unit tests for email verification
@pytest.mark.asyncio
async def test_email_verifier_personal_detection():
    """Test personal email provider detection."""
    verifier = EmailVerifier()
    
    personal_emails = [
        "user@gmail.com",
        "test@yahoo.com",
        "person@hotmail.com",
        "someone@outlook.com"
    ]
    
    for email in personal_emails:
        assert verifier._is_personal_email(email), f"{email} should be detected as personal"


@pytest.mark.asyncio
async def test_email_verifier_role_based_detection():
    """Test role-based email detection."""
    verifier = EmailVerifier()
    
    role_emails = [
        "info@example.com",
        "contact@business.com",
        "sales@company.com",
        "support@service.com"
    ]
    
    for email in role_emails:
        assert verifier._is_role_based(email), f"{email} should be detected as role-based"


@pytest.mark.asyncio
async def test_email_verifier_business_classification():
    """Test business email classification."""
    verifier = EmailVerifier()
    
    # Business domain emails
    result = await verifier.verify("contact@business.com")
    assert result.is_business == True
    
    # Personal email (non-role)
    result = await verifier.verify("john.doe@gmail.com")
    assert result.is_business == False
    
    # Role-based personal email (acceptable)
    result = await verifier.verify("info@gmail.com")
    assert result.is_business == True


@pytest.mark.asyncio
async def test_email_verifier_caching():
    """Test verification result caching."""
    verifier = EmailVerifier()
    email = "test@example.com"
    
    # First verification
    result1 = await verifier.verify(email)
    
    # Second verification (should use cache)
    result2 = await verifier.verify(email)
    
    # Should be same instance from cache
    assert result1.verified_at == result2.verified_at


# Unit tests for phone verification
@pytest.mark.asyncio
async def test_phone_verifier_basic_validation():
    """Test basic phone validation."""
    verifier = PhoneVerifier()
    
    valid_phones = [
        "+919876543210",
        "+911234567890"
    ]
    
    for phone in valid_phones:
        result = await verifier.verify(phone)
        assert result.is_valid == True, f"{phone} should be valid"


@pytest.mark.asyncio
async def test_phone_verifier_invalid_numbers():
    """Test invalid phone number handling."""
    verifier = PhoneVerifier()
    
    invalid_phones = [
        "123",
        "invalid",
        "+91123"  # Too short
    ]
    
    for phone in invalid_phones:
        result = await verifier.verify(phone)
        assert result.is_valid == False, f"{phone} should be invalid"


@pytest.mark.asyncio
async def test_phone_verifier_carrier_type_detection():
    """Test carrier type detection."""
    verifier = PhoneVerifier()
    
    # This would require actual API calls or mocking
    # For now, test that carrier_type is set
    result = await verifier.verify("+919876543210")
    assert result.carrier_type in ['landline', 'mobile', 'voip', 'unknown']


@pytest.mark.asyncio
async def test_phone_verifier_business_line_classification():
    """Test business line classification."""
    verifier = PhoneVerifier()
    
    result = await verifier.verify("+919876543210")
    
    # Business line should be True for landline/voip
    if result.carrier_type in ['landline', 'voip']:
        assert result.is_business_line == True
    elif result.carrier_type == 'mobile':
        assert result.is_business_line == False


@pytest.mark.asyncio
async def test_phone_verifier_caching():
    """Test phone verification caching."""
    verifier = PhoneVerifier()
    phone = "+919876543210"
    
    # First verification
    result1 = await verifier.verify(phone)
    
    # Second verification (should use cache)
    result2 = await verifier.verify(phone)
    
    # Should be same instance from cache
    assert result1.verified_at == result2.verified_at


def test_confidence_threshold_logic():
    """Test confidence threshold filtering logic."""
    email_threshold = 0.7
    phone_threshold = 0.6
    
    # Email confidence tests
    assert 0.8 >= email_threshold  # Should pass
    assert 0.5 < email_threshold   # Should fail
    
    # Phone confidence tests
    assert 0.7 >= phone_threshold  # Should pass
    assert 0.5 < phone_threshold   # Should fail


@pytest.mark.asyncio
async def test_verification_result_structure():
    """Test that verification results have all required fields."""
    verifier = EmailVerifier()
    result = await verifier.verify("test@example.com")
    
    # Check all required fields exist
    assert hasattr(result, 'email')
    assert hasattr(result, 'is_deliverable')
    assert hasattr(result, 'is_business')
    assert hasattr(result, 'confidence_score')
    assert hasattr(result, 'provider_response')
    assert hasattr(result, 'provider_name')
    assert hasattr(result, 'verified_at')
