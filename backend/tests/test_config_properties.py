"""Property-based tests for configuration validation.

Feature: devsync-sales-ai
Tests configuration loading, validation, and default values.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from pydantic import ValidationError

from app.config import Settings


# Custom strategies for configuration values
@st.composite
def valid_database_url(draw):
    """Generate valid PostgreSQL connection strings."""
    user = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Nd'))))
    password = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Nd', 'Lu'))))
    host = draw(st.sampled_from(['localhost', '127.0.0.1', 'db', 'postgres']))
    port = draw(st.integers(min_value=5432, max_value=5432))
    dbname = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Nd'))))
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


@st.composite
def valid_email(draw):
    """Generate valid email addresses."""
    local = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Nd'))))
    domain = draw(st.sampled_from(['example.com', 'test.com', 'company.com']))
    return f"{local}@{domain}"


@st.composite
def valid_time_string(draw):
    """Generate valid time strings in HH:MM format."""
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    return f"{hour:02d}:{minute:02d}"


@st.composite
def valid_timezone(draw):
    """Generate valid timezone strings."""
    return draw(st.sampled_from([
        'Asia/Kolkata', 'America/New_York', 'Europe/London',
        'Asia/Tokyo', 'Australia/Sydney', 'UTC'
    ]))


# Property 54: Required config validation
# Feature: devsync-sales-ai, Property 54: Required config validation
@settings(max_examples=100)
@given(
    database_url=valid_database_url(),
    email_from=valid_email(),
    business_address=st.text(min_size=10, max_size=200)
)
def test_property_54_required_config_validation(database_url, email_from, business_address):
    """
    Feature: devsync-sales-ai, Property 54: Required config validation
    
    For any required environment variable that is missing at startup,
    the system must fail to start and display an error message indicating
    which variable is required.
    
    Validates: Requirements 17.2
    """
    # Test 1: All required fields present - should succeed
    try:
        config = Settings(
            database_url=database_url,
            email_from=email_from,
            business_address=business_address,
            # Provide minimal required providers
            sendgrid_api_key="test_key",
            abstractapi_key="test_key",
            numverify_key="test_key",
            openai_api_key="test_key"
        )
        assert config.database_url is not None
        assert config.email_from == email_from
        assert config.business_address == business_address
    except ValidationError:
        pytest.fail("Valid configuration was rejected")
    
    # Test 2: Missing database_url - should fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            email_from=email_from,
            business_address=business_address,
            sendgrid_api_key="test_key",
            abstractapi_key="test_key",
            numverify_key="test_key",
            openai_api_key="test_key"
        )
    
    # Verify error message mentions the missing field
    error_str = str(exc_info.value)
    assert 'database_url' in error_str.lower()
    
    # Test 3: Missing email_from - should fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            database_url=database_url,
            business_address=business_address,
            sendgrid_api_key="test_key",
            abstractapi_key="test_key",
            numverify_key="test_key",
            openai_api_key="test_key"
        )
    
    error_str = str(exc_info.value)
    assert 'email_from' in error_str.lower()
    
    # Test 4: Missing business_address - should fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            database_url=database_url,
            email_from=email_from,
            sendgrid_api_key="test_key",
            abstractapi_key="test_key",
            numverify_key="test_key",
            openai_api_key="test_key"
        )
    
    error_str = str(exc_info.value)
    assert 'business_address' in error_str.lower()


# Property 55: Invalid config rejection
# Feature: devsync-sales-ai, Property 55: Invalid config rejection
@settings(max_examples=100)
@given(
    daily_cap=st.integers(),
    confidence=st.floats(allow_nan=False, allow_infinity=False),
    time_str=st.text(max_size=10)
)
def test_property_55_invalid_config_rejection(daily_cap, confidence, time_str):
    """
    Feature: devsync-sales-ai, Property 55: Invalid config rejection
    
    For any configuration value that is invalid (negative daily cap,
    invalid timezone), the system must validate at startup and fail
    with a descriptive error message.
    
    Validates: Requirements 17.3
    """
    base_config = {
        'database_url': 'postgresql://user:pass@localhost:5432/test',
        'email_from': 'test@example.com',
        'business_address': 'Test Address',
        'sendgrid_api_key': 'test_key',
        'abstractapi_key': 'test_key',
        'numverify_key': 'test_key',
        'openai_api_key': 'test_key'
    }
    
    # Test 1: Invalid daily_email_cap (negative or zero)
    if daily_cap < 1 or daily_cap > 10000:
        with pytest.raises(ValidationError) as exc_info:
            Settings(**base_config, daily_email_cap=daily_cap)
        
        error_str = str(exc_info.value)
        assert 'daily_email_cap' in error_str.lower() or 'greater than or equal to 1' in error_str.lower()
    else:
        # Valid cap should work
        config = Settings(**base_config, daily_email_cap=daily_cap)
        assert config.daily_email_cap == daily_cap
    
    # Test 2: Invalid confidence threshold (outside 0.0-1.0)
    if confidence < 0.0 or confidence > 1.0:
        with pytest.raises(ValidationError) as exc_info:
            Settings(**base_config, email_confidence_threshold=confidence)
        
        error_str = str(exc_info.value)
        assert 'email_confidence_threshold' in error_str.lower() or 'less than or equal to 1' in error_str.lower()
    else:
        # Valid confidence should work
        config = Settings(**base_config, email_confidence_threshold=confidence)
        assert config.email_confidence_threshold == confidence
    
    # Test 3: Invalid time format
    # Valid format is HH:MM
    valid_time_pattern = time_str.count(':') == 1
    if valid_time_pattern:
        try:
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            valid_time_pattern = 0 <= hours <= 23 and 0 <= minutes <= 59
        except (ValueError, IndexError):
            valid_time_pattern = False
    
    if not valid_time_pattern:
        with pytest.raises(ValidationError) as exc_info:
            Settings(**base_config, email_send_time=time_str)
        
        error_str = str(exc_info.value)
        assert 'time' in error_str.lower() or 'format' in error_str.lower()
    else:
        # Valid time should work
        config = Settings(**base_config, email_send_time=time_str)
        assert config.email_send_time == time_str


# Property 57: Default value usage
# Feature: devsync-sales-ai, Property 57: Default value usage
@settings(max_examples=100)
@given(
    database_url=valid_database_url(),
    email_from=valid_email(),
    business_address=st.text(min_size=10, max_size=200)
)
def test_property_57_default_value_usage(database_url, email_from, business_address):
    """
    Feature: devsync-sales-ai, Property 57: Default value usage
    
    For any optional configuration not provided, the system must use
    the documented default value (e.g., daily caps of 100, approval
    mode enabled, 30-day cooldown).
    
    Validates: Requirements 17.5
    """
    # Create config with only required fields
    config = Settings(
        database_url=database_url,
        email_from=email_from,
        business_address=business_address,
        # Provide minimal required providers
        sendgrid_api_key="test_key",
        abstractapi_key="test_key",
        numverify_key="test_key",
        openai_api_key="test_key"
    )
    
    # Verify documented defaults are used
    assert config.daily_email_cap == 100, "Default daily_email_cap should be 100"
    assert config.daily_call_cap == 100, "Default daily_call_cap should be 100"
    assert config.cooldown_days == 30, "Default cooldown_days should be 30"
    assert config.approval_mode is True, "Default approval_mode should be True"
    assert config.dry_run_mode is True, "Default dry_run_mode should be True"
    assert config.timezone == "Asia/Kolkata", "Default timezone should be Asia/Kolkata"
    assert config.email_send_time == "10:00", "Default email_send_time should be 10:00"
    assert config.per_domain_hourly_limit == 5, "Default per_domain_hourly_limit should be 5"
    assert config.call_window_start == "11:00", "Default call_window_start should be 11:00"
    assert config.call_window_end == "17:00", "Default call_window_end should be 17:00"
    assert config.call_weekdays_only is True, "Default call_weekdays_only should be True"
    assert config.email_confidence_threshold == 0.7, "Default email_confidence_threshold should be 0.7"
    assert config.phone_confidence_threshold == 0.6, "Default phone_confidence_threshold should be 0.6"
    assert config.verification_cache_days == 30, "Default verification_cache_days should be 30"
    assert config.max_retry_attempts == 3, "Default max_retry_attempts should be 3"
    assert config.retry_base_delay == 1.0, "Default retry_base_delay should be 1.0"
    assert config.retry_max_delay == 60.0, "Default retry_max_delay should be 60.0"
    assert config.circuit_breaker_threshold == 5, "Default circuit_breaker_threshold should be 5"
    assert config.circuit_breaker_timeout == 60, "Default circuit_breaker_timeout should be 60"
    assert config.log_retention_days == 90, "Default log_retention_days should be 90"
    assert config.outreach_log_retention_days == 90, "Default outreach_log_retention_days should be 90"
    assert config.log_level == "INFO", "Default log_level should be INFO"
    assert config.ai_timeout_seconds == 5.0, "Default ai_timeout_seconds should be 5.0"
    assert config.ai_max_tokens == 150, "Default ai_max_tokens should be 150"
    assert config.approval_queue_expiry_days == 7, "Default approval_queue_expiry_days should be 7"
    assert config.email_from_name == "DevSync Innovation", "Default email_from_name should be DevSync Innovation"
    assert config.smtp_port == 587, "Default smtp_port should be 587"
    assert config.scraper_rate_limit_delay == 1.0, "Default scraper_rate_limit_delay should be 1.0"
    assert config.scraper_max_retries == 3, "Default scraper_max_retries should be 3"
    
    # Verify default approved sources list
    expected_sources = ["google_maps", "justdial", "indiamart", "yelp", "linkedin_company"]
    assert config.approved_sources == expected_sources, f"Default approved_sources should be {expected_sources}"
    
    # Verify default operator_emails is empty list
    assert config.operator_emails == [], "Default operator_emails should be empty list"


# Additional unit tests for specific validation logic
def test_timezone_validation():
    """Test timezone validation."""
    base_config = {
        'database_url': 'postgresql://user:pass@localhost:5432/test',
        'email_from': 'test@example.com',
        'business_address': 'Test Address',
        'sendgrid_api_key': 'test_key',
        'abstractapi_key': 'test_key',
        'numverify_key': 'test_key',
        'openai_api_key': 'test_key'
    }
    
    # Valid timezone
    config = Settings(**base_config, timezone='America/New_York')
    assert config.timezone == 'America/New_York'
    
    # Invalid timezone
    with pytest.raises(ValidationError) as exc_info:
        Settings(**base_config, timezone='Invalid/Timezone')
    
    assert 'timezone' in str(exc_info.value).lower()


def test_email_provider_validation():
    """Test that at least one email provider must be configured."""
    base_config = {
        'database_url': 'postgresql://user:pass@localhost:5432/test',
        'email_from': 'test@example.com',
        'business_address': 'Test Address',
        'abstractapi_key': 'test_key',
        'numverify_key': 'test_key',
        'openai_api_key': 'test_key'
    }
    
    # No email provider - should fail validation
    with pytest.raises(ValueError) as exc_info:
        config = Settings(**base_config)
        config.validate_email_provider()
    
    assert 'email provider' in str(exc_info.value).lower()
    
    # With SendGrid - should pass
    config = Settings(**base_config, sendgrid_api_key='test_key')
    assert config.validate_email_provider() is True
    
    # With Mailgun - should pass
    config = Settings(**base_config, mailgun_api_key='test_key', mailgun_domain='test.com')
    assert config.validate_email_provider() is True
    
    # With SMTP - should pass
    config = Settings(**base_config, smtp_host='smtp.test.com', smtp_user='user', smtp_password='pass')
    assert config.validate_email_provider() is True


def test_verification_provider_validation():
    """Test that verification providers must be configured."""
    base_config = {
        'database_url': 'postgresql://user:pass@localhost:5432/test',
        'email_from': 'test@example.com',
        'business_address': 'Test Address',
        'sendgrid_api_key': 'test_key',
        'openai_api_key': 'test_key'
    }
    
    # No email verifier - should fail
    with pytest.raises(ValueError) as exc_info:
        config = Settings(**base_config, numverify_key='test_key')
        config.validate_verification_provider()
    
    assert 'email verification' in str(exc_info.value).lower()
    
    # No phone verifier - should fail
    with pytest.raises(ValueError) as exc_info:
        config = Settings(**base_config, abstractapi_key='test_key')
        config.validate_verification_provider()
    
    assert 'phone verification' in str(exc_info.value).lower()
    
    # Both present - should pass
    config = Settings(**base_config, abstractapi_key='test_key', numverify_key='test_key')
    assert config.validate_verification_provider() is True


def test_ai_provider_validation():
    """Test that at least one AI provider must be configured."""
    base_config = {
        'database_url': 'postgresql://user:pass@localhost:5432/test',
        'email_from': 'test@example.com',
        'business_address': 'Test Address',
        'sendgrid_api_key': 'test_key',
        'abstractapi_key': 'test_key',
        'numverify_key': 'test_key'
    }
    
    # No AI provider - should fail
    with pytest.raises(ValueError) as exc_info:
        config = Settings(**base_config)
        config.validate_ai_provider()
    
    assert 'ai provider' in str(exc_info.value).lower()
    
    # With OpenAI - should pass
    config = Settings(**base_config, openai_api_key='test_key')
    assert config.validate_ai_provider() is True
    
    # With AIMLAPI - should pass
    config = Settings(**base_config, aimlapi_key='test_key')
    assert config.validate_ai_provider() is True


def test_sensitive_data_masking():
    """Test that sensitive values are masked in logs."""
    config = Settings(
        database_url='postgresql://user:pass@localhost:5432/test',
        email_from='test@example.com',
        business_address='Test Address',
        sendgrid_api_key='sk_test_1234567890abcdef',
        abstractapi_key='test_key',
        numverify_key='test_key',
        openai_api_key='sk-1234567890abcdef'
    )
    
    # Test masking
    masked = config.mask_sensitive('sk_test_1234567890abcdef')
    assert masked == 'sk_t...cdef'
    assert 'sk_test_1234567890abcdef' not in masked
    
    # Test short values
    masked_short = config.mask_sensitive('short')
    assert masked_short == '****'
    
    # Test None
    masked_none = config.mask_sensitive(None)
    assert masked_none == 'None'
