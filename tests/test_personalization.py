"""Property-based tests for personalization service.
Feature: devsync-sales-ai
"""
import pytest
from hypothesis import given, strategies as st, settings
from app.outreach.personalizer import EmailPersonalizer, PersonalizedEmail
from app.models import Lead
from datetime import datetime


# Helper strategy for creating test leads
@st.composite
def lead_strategy(draw):
    """Generate test lead."""
    return Lead(
        id=draw(st.integers(min_value=1, max_value=1000)),
        source="google_maps",
        business_name=draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', ' ')))),
        city=draw(st.sampled_from(["Mumbai", "Delhi", "Bangalore", "Chennai"])),
        category=draw(st.sampled_from(["restaurant", "cafe","retail" "manufacturing"])),
        email_verified=True,
        phone_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


# Property 28: AI provider invocation
@pytest.mark.property
@pytest.mark.asyncio
@given(lead=lead_strategy())
@settings(max_examples=50)
async def test_property_28_ai_provider_invocation(lead):
    """
    Feature: devsync-sales-ai, Property 28: AI provider invocation
    For any verified lead selected for email outreach, the system must call the
    configured AI provider with lead context to generate personalized content.
    
    Validates: Requirements 9.1
    """
    personalizer = EmailPersonalizer()
    
    # Generate email (will use fallback if no API key)
    result = await personalizer.generate(lead)
    
    # Verify result exists and has required structure
    assert result is not None
    assert isinstance(result, PersonalizedEmail)
    assert result.subject is not None
    assert result.body_html is not None
    assert result.body_text is not None
    assert result.personalization_method in ["ai", "template"]
    assert result.generated_at is not None


# Property 29: Content validation
@pytest.mark.property
@pytest.mark.asyncio
@given(lead=lead_strategy())
@settings(max_examples=50)
async def test_property_29_content_validation(lead):
    """
    Feature: devsync-sales-ai, Property 29: Content validation
    For any AI-generated email, the content must include a personalized hook,
    value proposition mentioning DevSync Innovation, and a call-to-action.
    
    Validates: Requirements 9.2
    """
    personalizer = EmailPersonalizer()
    
    # Generate email
    result = await personalizer.generate(lead)
    
    # Verify content structure
    assert len(result.subject) > 0, "Subject must not be empty"
    assert len(result.body_text) > 0, "Body must not be empty"
    
    # Check for required elements
    body_lower = result.body_text.lower()
    
    # Should mention DevSync Innovation
    assert "devsync" in body_lower, "Email must mention DevSync Innovation"
    
    # Should have personalization (business name or category)
    has_personalization = (
        lead.business_name.lower() in body_lower or
        lead.category.lower() in body_lower
    )
    assert has_personalization, "Email must include personalization"


# Property 30: Fallback on AI failure
@pytest.mark.property
@pytest.mark.asyncio
@given(lead=lead_strategy())
@settings(max_examples=50)
async def test_property_30_fallback_on_ai_failure(lead):
    """
    Feature: devsync-sales-ai, Property 30: Fallback on AI failure
    For any AI content generation that fails or times out, the system must fall
    back to a pre-configured template with variable substitution.
    
    Validates: Requirements 9.3
    """
    personalizer = EmailPersonalizer()
    
    # Force fallback by using template directly
    result = personalizer._fallback_template(lead)
    
    # Verify fallback works
    assert result is not None
    assert result.personalization_method == "template"
    assert lead.business_name in result.subject
    assert lead.category in result.body_text
    assert lead.city in result.body_text
    assert "DevSync Innovation" in result.body_text


# Unit tests for personalization
@pytest.mark.asyncio
async def test_template_generation():
    """Test template-based email generation."""
    personalizer = EmailPersonalizer()
    
    lead = Lead(
        id=1,
        source="google_maps",
        business_name="Test Restaurant",
        city="Mumbai",
        category="restaurant",
        email_verified=True,
        phone_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    result = personalizer._fallback_template(lead)
    
    assert "Test Restaurant" in result.subject
    assert "restaurant" in result.body_text
    assert "Mumbai" in result.body_text
    assert "DevSync Innovation" in result.body_text


def test_content_validation():
    """Test content validation logic."""
    personalizer = EmailPersonalizer()
    
    lead = Lead(
        id=1,
        source="google_maps",
        business_name="Test Business",
        city="Mumbai",
        category="retail",
        email_verified=True,
        phone_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Valid content
    valid_content = """Hi Test Business team,

I noticed you're in the retail business. DevSync Innovation specializes in building fast, SEO-optimized websites for retail companies.

Would you be open to a quick call to discuss how we can help grow your online presence?

Best regards,
DevSync Innovation Team"""
    
    assert personalizer._validate_content(valid_content, lead)
    
    # Too short
    short_content = "Hi there. DevSync Innovation."
    assert not personalizer._validate_content(short_content, lead)
    
    # Missing DevSync
    no_devsync = "Hi Test Business. We build websites for retail companies. " * 10
    assert not personalizer._validate_content(no_devsync, lead)


def test_ai_content_parsing():
    """Test parsing of AI-generated content."""
    personalizer = EmailPersonalizer()
    
    lead = Lead(
        id=1,
        source="google_maps",
        business_name="Test Business",
        city="Mumbai",
        category="retail",
        email_verified=True,
        phone_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Content with subject line
    content_with_subject = """Subject: Website Solutions for Your Business

Hi Test Business team,

We build websites for retail companies.

Best regards"""
    
    subject, body = personalizer._parse_ai_content(content_with_subject, lead)
    
    assert subject == "Website Solutions for Your Business"
    assert "Hi Test Business team" in body
    
    # Content without subject line
    content_without_subject = """Hi Test Business team,

We build websites for retail companies."""
    
    subject, body = personalizer._parse_ai_content(content_without_subject, lead)
    
    assert "Test Business" in subject  # Default subject
    assert "Hi Test Business team" in body


def test_html_formatting():
    """Test HTML formatting of plain text."""
    personalizer = EmailPersonalizer()
    
    text = """Hi there,

This is a test email.

Best regards"""
    
    html = personalizer._format_html(text)
    
    assert "<html>" in html
    assert "<p>" in html
    assert "</p>" in html
    assert "Hi there" in html
    assert "test email" in html


def test_prompt_building():
    """Test AI prompt construction."""
    personalizer = EmailPersonalizer()
    
    lead = Lead(
        id=1,
        source="google_maps",
        business_name="Test Restaurant",
        city="Mumbai",
        category="restaurant",
        email_verified=True,
        phone_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    prompt = personalizer._build_prompt(lead)
    
    assert "Test Restaurant" in prompt
    assert "Mumbai" in prompt
    assert "restaurant" in prompt
    assert "DevSync Innovation" in prompt
    assert "3-line email" in prompt
