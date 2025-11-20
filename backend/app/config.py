"""Configuration management with environment variable validation."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator, PostgresDsn
import os


class Settings(BaseSettings):
    """Application settings with validation."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database
    DATABASE_URL: str = Field(
        ...,
        description="Database connection string (PostgreSQL or SQLite for testing)"
    )
    
    # Email Provider (at least one required)
    SENDGRID_API_KEY: Optional[str] = Field(None, description="SendGrid API key")
    MAILGUN_API_KEY: Optional[str] = Field(None, description="Mailgun API key")
    MAILGUN_DOMAIN: Optional[str] = Field(None, description="Mailgun domain")
    SMTP_HOST: Optional[str] = Field(None, description="SMTP server host")
    SMTP_PORT: int = Field(587, description="SMTP server port")
    SMTP_USER: Optional[str] = Field(None, description="SMTP username")
    SMTP_PASSWORD: Optional[str] = Field(None, description="SMTP password")
    
    # Email Configuration
    EMAIL_FROM: str = Field(
        ...,
        description="From email address"
    )
    EMAIL_FROM_NAME: str = Field(
        "DevSync Innovation",
        description="From name"
    )
    BUSINESS_ADDRESS: str = Field(
        ...,
        description="Physical business address for compliance"
    )
    
    # Verification Providers
    ABSTRACTAPI_KEY: Optional[str] = Field(None, description="AbstractAPI key for email verification")
    ZEROBOUNCE_API_KEY: Optional[str] = Field(None, description="ZeroBounce API key")
    HUNTER_API_KEY: Optional[str] = Field(None, description="Hunter.io API key")
    NUMVERIFY_KEY: Optional[str] = Field(None, description="NumVerify API key for phone verification")
    
    # Telephony - Vonage
    VONAGE_API_KEY: Optional[str] = Field(None, description="Vonage API Key")
    VONAGE_API_SECRET: Optional[str] = Field(None, description="Vonage API Secret")
    VONAGE_PHONE_NUMBER: Optional[str] = Field(None, description="Vonage phone number")
    
    # Telephony - Twilio (alternative)
    TWILIO_ACCOUNT_SID: Optional[str] = Field(None, description="Twilio Account SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(None, description="Twilio Auth Token")
    TWILIO_PHONE_NUMBER: Optional[str] = Field(None, description="Twilio phone number")
    
    # AI Services
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API key")
    AIMLAPI_KEY: Optional[str] = Field(None, description="AIMLAPI key")
    ELEVENLABS_API_KEY: Optional[str] = Field(None, description="ElevenLabs API key for TTS")
    
    # Operational Settings
    DAILY_EMAIL_CAP: int = Field(
        100,
        ge=1,
        le=10000,
        description="Maximum emails per day"
    )
    DAILY_CALL_CAP: int = Field(
        100,
        ge=1,
        le=10000,
        description="Maximum calls per day"
    )
    COOLDOWN_DAYS: int = Field(
        30,
        ge=1,
        le=365,
        description="Days between contacts to same lead"
    )
    APPROVAL_MODE: bool = Field(
        True,
        description="Require approval before sending"
    )
    DRY_RUN_MODE: bool = Field(
        True,
        description="Simulate outreach without actually sending"
    )
    TIMEZONE: str = Field(
        "Asia/Kolkata",
        description="Timezone for scheduling"
    )
    
    # Scraping Configuration
    GOOGLE_MAPS_API_KEY: Optional[str] = Field(None, description="Google Maps API key")
    APPROVED_SOURCES: list[str] = Field(
        default=["google_maps", "justdial", "indiamart", "yelp", "linkedin_company"],
        description="Approved lead sources"
    )
    
    # Rate Limiting
    PER_DOMAIN_EMAIL_LIMIT: int = Field(5, description="Max emails per hour per domain")
    EMAIL_VERIFICATION_CONFIDENCE_THRESHOLD: float = Field(0.7, ge=0.0, le=1.0)
    PHONE_VERIFICATION_CONFIDENCE_THRESHOLD: float = Field(0.6, ge=0.0, le=1.0)
    
    # Scheduling
    EMAIL_SEND_TIME: str = Field("10:00", description="Daily email send time (HH:MM)")
    CALL_WINDOW_START: str = Field("11:00", description="Call window start (HH:MM)")
    CALL_WINDOW_END: str = Field("17:00", description="Call window end (HH:MM)")
    
    # Monitoring
    SENTRY_DSN: Optional[str] = Field(None, description="Sentry DSN for error tracking")
    LOG_LEVEL: str = Field("INFO", description="Logging level")
    
    # Redis (optional)
    REDIS_URL: Optional[str] = Field(None, description="Redis connection string")
    
    # Data Retention
    LOG_RETENTION_DAYS: int = Field(90, description="Days to retain logs")
    
    # Do Not Call Registry
    DNC_REGISTRY_FILE: Optional[str] = Field(None, description="Path to DNC registry file")
    
    @validator("DATABASE_URL", pre=True)
    def validate_database_url(cls, v):
        """Validate database URL is provided."""
        if not v:
            raise ValueError("DATABASE_URL is required")
        return v
    
    @validator("EMAIL_FROM")
    def validate_email_from(cls, v):
        """Validate email from address."""
        if not v or "@" not in v:
            raise ValueError("EMAIL_FROM must be a valid email address")
        return v
    
    @validator("BUSINESS_ADDRESS")
    def validate_business_address(cls, v):
        """Validate business address is provided."""
        if not v or len(v) < 10:
            raise ValueError("BUSINESS_ADDRESS must be a valid physical address")
        return v
    
    @validator("DAILY_EMAIL_CAP", "DAILY_CALL_CAP")
    def validate_caps(cls, v):
        """Validate daily caps are positive."""
        if v < 1:
            raise ValueError("Daily caps must be at least 1")
        return v
    
    @validator("TIMEZONE")
    def validate_timezone(cls, v):
        """Validate timezone string."""
        try:
            import pytz
            pytz.timezone(v)
        except Exception:
            raise ValueError(f"Invalid timezone: {v}")
        return v
    
    def mask_sensitive(self, key: str, value: str) -> str:
        """Mask sensitive configuration values for logging."""
        if not value:
            return "None"
        if len(value) <= 8:
            return "****"
        return f"{value[:4]}...{value[-4:]}"
    
    def get_masked_config(self) -> dict:
        """Get configuration with sensitive values masked."""
        sensitive_keys = [
            "SENDGRID_API_KEY", "MAILGUN_API_KEY", "SMTP_PASSWORD",
            "ABSTRACTAPI_KEY", "ZEROBOUNCE_API_KEY", "HUNTER_API_KEY",
            "NUMVERIFY_KEY", "TWILIO_AUTH_TOKEN", "OPENAI_API_KEY",
            "AIMLAPI_KEY", "ELEVENLABS_API_KEY", "SENTRY_DSN"
        ]
        
        config = self.model_dump()
        for key in sensitive_keys:
            if key in config and config[key]:
                config[key] = self.mask_sensitive(key, config[key])
        
        return config


# Global settings instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global settings
    if settings is None:
        settings = Settings()
    return settings


def validate_production_config():
    """Validate configuration for production deployment."""
    config = get_settings()
    
    errors = []
    
    # Check email provider is configured
    has_email_provider = any([
        config.SENDGRID_API_KEY,
        config.MAILGUN_API_KEY,
        config.SMTP_HOST
    ])
    if not has_email_provider:
        errors.append("No email provider configured (SendGrid, Mailgun, or SMTP)")
    
    # Check verification provider is configured
    has_email_verifier = any([
        config.ABSTRACTAPI_KEY,
        config.ZEROBOUNCE_API_KEY,
        config.HUNTER_API_KEY
    ])
    if not has_email_verifier:
        errors.append("No email verification provider configured")
    
    has_phone_verifier = any([
        config.NUMVERIFY_KEY,
        config.TWILIO_ACCOUNT_SID
    ])
    if not has_phone_verifier:
        errors.append("No phone verification provider configured")
    
    # Check AI provider for personalization
    has_ai_provider = any([
        config.OPENAI_API_KEY,
        config.AIMLAPI_KEY
    ])
    if not has_ai_provider:
        errors.append("No AI provider configured for personalization")
    
    # Warn if dry-run is disabled
    if not config.DRY_RUN_MODE:
        print("⚠️  WARNING: DRY_RUN_MODE is disabled. System will send real emails and make real calls.")
        print("⚠️  Ensure you have tested thoroughly and understand compliance requirements.")
    
    # Warn if approval mode is disabled
    if not config.APPROVAL_MODE:
        print("⚠️  WARNING: APPROVAL_MODE is disabled. Outreach will be sent automatically.")
        print("⚠️  Ensure you are monitoring campaign quality and compliance.")
    
    if errors:
        raise ValueError(f"Production configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return True
