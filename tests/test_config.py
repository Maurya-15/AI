"""Property-based tests for configuration validation.

Feature: devsync-sales-ai
"""

import pytest
from hypothesis import given, strategies as st, settings
from pydantic import ValidationError
from app.config import Settings
import os


# Property 54: Required config validation
@pytest.mark.property
@given(st.sampled_from(["DATABASE_URL", "EMAIL_FROM", "BUSINESS_ADDRESS"]))
@settings(max_examples=100)
def test_property_54_required_config_validation(required_field):
    """
    Feature: devsync-sales-ai, Property 54: Required config validation
    For any required environment variable that is missing at startup, the system
    must fail to start and display an error message indicating which variable is required.
    
    Validates: Requirements 17.2
    """
    # Save original env vars
    original_values = {}
    for field in ["DATABASE_URL", "EMAIL_FROM", "BUSINESS_ADDRESS"]:
        original_values[field] = os.environ.get(field)
    
    try:
        # Set valid values for all fields
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        os.environ["EMAIL_FROM"] = "test@example.com"
        os.environ["BUSINESS_ADDRESS"] = "123 Test Street, Test City, TC 12345"
        
        # Remove the required field being tested
        if required_field in os.environ:
            del os.environ[required_field]
        
        # Attempt to create settings - should fail
        with pytest.raises((ValidationError, ValueError)) as exc_info:
            Settings()
        
        # Verify error message mentions the missing field
        error_str = str(exc_info.value).lower()
        assert required_field.lower() in error_str or "required" in error_str
        
    finally:
        # Restore original env vars
        for field, value in original_values.items():
            if value is not None:
                os.environ[field] = value
            elif field in os.environ:
                del os.environ[field]


# Property 55: Invalid config rejection
@pytest.mark.property
@given(
    email=st.one_of(
        st.just(""),
        st.just("invalid"),
        st.just("@example.com"),
        st.just("test@"),
        st.text(min_size=1, max_size=10).filter(lambda x: "@" not in x)
    )
)
@settings(max_examples=100)
def test_property_55_invalid_config_rejection(email):
    """
    Feature: devsync-sales-ai, Property 55: Invalid config rejection
    For any configuration value that is invalid (negative daily cap, invalid timezone),
    the system must validate at startup and fail with a descriptive error message.
    
    Validates: Requirements 17.3
    """
    # Save original env vars
    original_email = os.environ.get("EMAIL_FROM")
    original_db = os.environ.get("DATABASE_URL")
    original_addr = os.environ.get("BUSINESS_ADDRESS")
    
    try:
        # Set required fields
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        os.environ["BUSINESS_ADDRESS"] = "123 Test Street, Test City, TC 12345"
        os.environ["EMAIL_FROM"] = email
        
        # Attempt to create settings with invalid email - should fail
        with pytest.raises((ValidationError, ValueError)):
            Settings()
            
    finally:
        # Restore original env vars
        if original_email is not None:
            os.environ["EMAIL_FROM"] = original_email
        elif "EMAIL_FROM" in os.environ:
            del os.environ["EMAIL_FROM"]
        if original_db is not None:
            os.environ["DATABASE_URL"] = original_db
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]
        if original_addr is not None:
            os.environ["BUSINESS_ADDRESS"] = original_addr
        elif "BUSINESS_ADDRESS" in os.environ:
            del os.environ["BUSINESS_ADDRESS"]


@pytest.mark.property
@given(cap=st.integers(max_value=0))
@settings(max_examples=100)
def test_property_55_invalid_daily_caps(cap):
    """
    Feature: devsync-sales-ai, Property 55: Invalid config rejection
    Test that negative or zero daily caps are rejected.
    
    Validates: Requirements 17.3
    """
    # Save original env vars
    original_values = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "EMAIL_FROM": os.environ.get("EMAIL_FROM"),
        "BUSINESS_ADDRESS": os.environ.get("BUSINESS_ADDRESS"),
        "DAILY_EMAIL_CAP": os.environ.get("DAILY_EMAIL_CAP")
    }
    
    try:
        # Set required fields
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        os.environ["EMAIL_FROM"] = "test@example.com"
        os.environ["BUSINESS_ADDRESS"] = "123 Test Street, Test City, TC 12345"
        os.environ["DAILY_EMAIL_CAP"] = str(cap)
        
        # Attempt to create settings with invalid cap - should fail
        with pytest.raises((ValidationError, ValueError)):
            Settings()
            
    finally:
        # Restore original env vars
        for field, value in original_values.items():
            if value is not None:
                os.environ[field] = value
            elif field in os.environ:
                del os.environ[field]


@pytest.mark.property
@given(timezone=st.text(min_size=1, max_size=20).filter(lambda x: x not in ["Asia/Kolkata", "UTC", "America/New_York"]))
@settings(max_examples=50)
def test_property_55_invalid_timezone(timezone):
    """
    Feature: devsync-sales-ai, Property 55: Invalid config rejection
    Test that invalid timezones are rejected.
    
    Validates: Requirements 17.3
    """
    # Save original env vars
    original_values = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "EMAIL_FROM": os.environ.get("EMAIL_FROM"),
        "BUSINESS_ADDRESS": os.environ.get("BUSINESS_ADDRESS"),
        "TIMEZONE": os.environ.get("TIMEZONE")
    }
    
    try:
        # Set required fields
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        os.environ["EMAIL_FROM"] = "test@example.com"
        os.environ["BUSINESS_ADDRESS"] = "123 Test Street, Test City, TC 12345"
        os.environ["TIMEZONE"] = timezone
        
        # Attempt to create settings with invalid timezone - should fail
        with pytest.raises((ValidationError, ValueError)):
            Settings()
            
    finally:
        # Restore original env vars
        for field, value in original_values.items():
            if value is not None:
                os.environ[field] = value
            elif field in os.environ:
                del os.environ[field]


# Property 57: Default value usage
@pytest.mark.property
@given(
    dry_run=st.booleans(),
    approval=st.booleans()
)
@settings(max_examples=100)
def test_property_57_default_value_usage(dry_run, approval):
    """
    Feature: devsync-sales-ai, Property 57: Default value usage
    For any optional configuration not provided, the system must use the
    documented default value (e.g., daily caps of 100, approval mode enabled, 30-day cooldown).
    
    Validates: Requirements 17.5
    """
    # Save original env vars
    original_values = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "EMAIL_FROM": os.environ.get("EMAIL_FROM"),
        "BUSINESS_ADDRESS": os.environ.get("BUSINESS_ADDRESS"),
        "DAILY_EMAIL_CAP": os.environ.get("DAILY_EMAIL_CAP"),
        "DAILY_CALL_CAP": os.environ.get("DAILY_CALL_CAP"),
        "COOLDOWN_DAYS": os.environ.get("COOLDOWN_DAYS"),
        "DRY_RUN_MODE": os.environ.get("DRY_RUN_MODE"),
        "APPROVAL_MODE": os.environ.get("APPROVAL_MODE"),
        "TIMEZONE": os.environ.get("TIMEZONE"),
        "PER_DOMAIN_EMAIL_LIMIT": os.environ.get("PER_DOMAIN_EMAIL_LIMIT")
    }
    
    try:
        # Set only required fields
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        os.environ["EMAIL_FROM"] = "test@example.com"
        os.environ["BUSINESS_ADDRESS"] = "123 Test Street, Test City, TC 12345"
        
        # Optionally set some boolean flags
        if dry_run is not None:
            os.environ["DRY_RUN_MODE"] = str(dry_run).lower()
        else:
            if "DRY_RUN_MODE" in os.environ:
                del os.environ["DRY_RUN_MODE"]
                
        if approval is not None:
            os.environ["APPROVAL_MODE"] = str(approval).lower()
        else:
            if "APPROVAL_MODE" in os.environ:
                del os.environ["APPROVAL_MODE"]
        
        # Remove optional fields to test defaults
        for field in ["DAILY_EMAIL_CAP", "DAILY_CALL_CAP", "COOLDOWN_DAYS", "TIMEZONE", "PER_DOMAIN_EMAIL_LIMIT"]:
            if field in os.environ:
                del os.environ[field]
        
        # Create settings - should succeed with defaults
        settings = Settings()
        
        # Verify defaults are used
        assert settings.DAILY_EMAIL_CAP == 100, "Default email cap should be 100"
        assert settings.DAILY_CALL_CAP == 100, "Default call cap should be 100"
        assert settings.COOLDOWN_DAYS == 30, "Default cooldown should be 30 days"
        assert settings.TIMEZONE == "Asia/Kolkata", "Default timezone should be Asia/Kolkata"
        assert settings.PER_DOMAIN_EMAIL_LIMIT == 5, "Default per-domain limit should be 5"
        
        # Verify provided values are used
        if dry_run is not None:
            assert settings.DRY_RUN_MODE == dry_run
        if approval is not None:
            assert settings.APPROVAL_MODE == approval
            
    finally:
        # Restore original env vars
        for field, value in original_values.items():
            if value is not None:
                os.environ[field] = value
            elif field in os.environ:
                del os.environ[field]


# Unit tests for specific scenarios
def test_config_loads_successfully():
    """Test that configuration loads with valid values."""
    # Save original env vars
    original_values = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "EMAIL_FROM": os.environ.get("EMAIL_FROM"),
        "BUSINESS_ADDRESS": os.environ.get("BUSINESS_ADDRESS")
    }
    
    try:
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        os.environ["EMAIL_FROM"] = "test@example.com"
        os.environ["BUSINESS_ADDRESS"] = "123 Test Street, Test City, TC 12345"
        
        settings = Settings()
        
        assert settings.DATABASE_URL is not None
        assert settings.EMAIL_FROM == "test@example.com"
        assert settings.BUSINESS_ADDRESS == "123 Test Street, Test City, TC 12345"
        assert settings.DRY_RUN_MODE == True  # Default
        assert settings.APPROVAL_MODE == True  # Default
        
    finally:
        for field, value in original_values.items():
            if value is not None:
                os.environ[field] = value
            elif field in os.environ:
                del os.environ[field]


def test_sensitive_data_masking():
    """Test that sensitive configuration values are masked in logs."""
    # Save original env vars
    original_values = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "EMAIL_FROM": os.environ.get("EMAIL_FROM"),
        "BUSINESS_ADDRESS": os.environ.get("BUSINESS_ADDRESS"),
        "SENDGRID_API_KEY": os.environ.get("SENDGRID_API_KEY")
    }
    
    try:
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        os.environ["EMAIL_FROM"] = "test@example.com"
        os.environ["BUSINESS_ADDRESS"] = "123 Test Street, Test City, TC 12345"
        os.environ["SENDGRID_API_KEY"] = "SG.1234567890abcdefghijklmnop"
        
        settings = Settings()
        masked_config = settings.get_masked_config()
        
        # Verify API key is masked
        assert "SENDGRID_API_KEY" in masked_config
        assert masked_config["SENDGRID_API_KEY"] != "SG.1234567890abcdefghijklmnop"
        assert "SG.1" in masked_config["SENDGRID_API_KEY"]
        assert "..." in masked_config["SENDGRID_API_KEY"]
        
    finally:
        for field, value in original_values.items():
            if value is not None:
                os.environ[field] = value
            elif field in os.environ:
                del os.environ[field]
