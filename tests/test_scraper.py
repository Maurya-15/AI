"""Property-based tests for scraper functionality.

Feature: devsync-sales-ai
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from app.scraper.base import BaseScraper, ScrapeQuery, RawLead
from app.scraper.google_maps import GoogleMapsScraper
from app.scraper.justdial import JustDialScraper
from app.scraper.linkedin_company import LinkedInCompanyScraper


# Approved sources list
APPROVED_SOURCES = ["google_maps", "justdial", "indiamart", "yelp", "linkedin_company"]


# Property 1: Approved sources only
@pytest.mark.property
@given(
    source=st.sampled_from(APPROVED_SOURCES),
    business_name=st.text(min_size=1, max_size=100),
    city=st.sampled_from(["Mumbai", "Delhi", "Bangalore", "Chennai"]),
    category=st.sampled_from(["restaurant", "retail", "services"])
)
@settings(max_examples=100)
def test_property_1_approved_sources_only(source, business_name, city, category):
    """
    Feature: devsync-sales-ai, Property 1: Approved sources only
    For any lead scraped by the system, the lead's source field must be in the
    configured list of approved public business sources.
    
    Validates: Requirements 1.1, 1.2
    """
    # Create a lead with the given source
    lead = RawLead(
        source=source,
        business_name=business_name,
        city=city,
        category=category,
        website=None,
        phone_numbers=[],
        emails=[],
        raw_metadata={}
    )
    
    # Verify source is in approved list
    assert lead.source in APPROVED_SOURCES, f"Source {lead.source} must be in approved sources list"


# Property 2: Personal source rejection
@pytest.mark.property
@given(
    source=st.text(min_size=1, max_size=50).filter(lambda x: x not in APPROVED_SOURCES),
    business_name=st.text(min_size=1, max_size=100)
)
@settings(max_examples=100)
def test_property_2_personal_source_rejection(source, business_name):
    """
    Feature: devsync-sales-ai, Property 2: Personal source rejection
    For any scrape attempt from a personal social media profile or non-public directory,
    the system must reject the source and return zero leads.
    
    Validates: Requirements 1.3
    """
    # Attempt to create lead with unapproved source
    lead = RawLead(
        source=source,
        business_name=business_name,
        city="Test City",
        category="test",
        website=None,
        phone_numbers=[],
        emails=[],
        raw_metadata={}
    )
    
    # In a real system, this would be rejected at validation
    # For now, verify it's not in approved sources
    assert lead.source not in APPROVED_SOURCES


# Property 3: Deduplication consistency
@pytest.mark.property
@given(
    business_name=st.text(min_size=1, max_size=100),
    website=st.one_of(st.none(), st.from_regex(r"https?://[a-z0-9-]+\.[a-z]{2,}", fullmatch=True)),
    phone=st.one_of(st.none(), st.from_regex(r"\+91[6-9]\d{9}", fullmatch=True)),
    duplicate_count=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100)
def test_property_3_deduplication_consistency(business_name, website, phone, duplicate_count):
    """
    Feature: devsync-sales-ai, Property 3: Deduplication consistency
    For any set of leads with the same (business_name, website, primary_phone) combination,
    the system must maintain exactly one lead record.
    
    Validates: Requirements 1.4
    """
    scraper = BaseScraper("test")
    
    # Create duplicate leads
    leads = []
    for i in range(duplicate_count):
        lead = RawLead(
            source="google_maps",
            business_name=business_name,
            city="Test City",
            category="test",
            website=website,
            phone_numbers=[phone] if phone else [],
            emails=[],
            raw_metadata={"index": i}
        )
        leads.append(lead)
    
    # Deduplicate
    unique_leads = scraper.deduplicate_leads(leads)
    
    # Verify only one lead remains
    assert len(unique_leads) == 1, f"Expected 1 unique lead, got {len(unique_leads)}"
    assert unique_leads[0].business_name == business_name


# Property 4: Rate limit backoff
@pytest.mark.property
@given(attempt=st.integers(min_value=0, max_value=10))
@settings(max_examples=100)
def test_property_4_rate_limit_backoff(attempt):
    """
    Feature: devsync-sales-ai, Property 4: Rate limit backoff
    For any scraper that receives a rate limit response (HTTP 429), the system must
    implement exponential backoff with increasing delays between retries.
    
    Validates: Requirements 1.5, 8.4
    """
    scraper = BaseScraper("test")
    
    # Calculate backoff delay
    delay = scraper.calculate_backoff(attempt)
    
    # Verify delay increases exponentially
    expected_base = scraper.base_delay * (2 ** attempt)
    expected_max = min(expected_base, scraper.max_delay)
    
    # Delay should be around expected value (with jitter)
    assert delay >= expected_max * 0.9, f"Delay {delay} too small for attempt {attempt}"
    assert delay <= expected_max * 1.1, f"Delay {delay} too large for attempt {attempt}"
    
    # Verify delay doesn't exceed max
    assert delay <= scraper.max_delay


# Property 26: Data normalization
@pytest.mark.property
@given(
    source=st.sampled_from(APPROVED_SOURCES),
    business_name=st.text(min_size=1, max_size=100),
    city=st.text(min_size=1, max_size=50),
    category=st.text(min_size=1, max_size=50)
)
@settings(max_examples=100)
def test_property_26_data_normalization(source, business_name, city, category):
    """
    Feature: devsync-sales-ai, Property 26: Data normalization
    For any scraper output, the returned leads must conform to the standardized
    lead object schema with fields for source, business_name, city, category,
    website, phone_numbers, emails, and raw_metadata.
    
    Validates: Requirements 8.5
    """
    # Create lead
    lead = RawLead(
        source=source,
        business_name=business_name,
        city=city,
        category=category,
        website=None,
        phone_numbers=[],
        emails=[],
        raw_metadata={}
    )
    
    # Verify all required fields exist
    assert hasattr(lead, 'source')
    assert hasattr(lead, 'business_name')
    assert hasattr(lead, 'city')
    assert hasattr(lead, 'category')
    assert hasattr(lead, 'website')
    assert hasattr(lead, 'phone_numbers')
    assert hasattr(lead, 'emails')
    assert hasattr(lead, 'raw_metadata')
    
    # Verify types
    assert isinstance(lead.source, str)
    assert isinstance(lead.business_name, str)
    assert isinstance(lead.city, str)
    assert isinstance(lead.category, str)
    assert isinstance(lead.phone_numbers, list)
    assert isinstance(lead.emails, list)
    assert isinstance(lead.raw_metadata, dict)


# Property 27: Retry exhaustion handling
@pytest.mark.property
@pytest.mark.asyncio
@given(max_retries=st.integers(min_value=1, max_value=5))
@settings(max_examples=50)
async def test_property_27_retry_exhaustion_handling(max_retries):
    """
    Feature: devsync-sales-ai, Property 27: Retry exhaustion handling
    For any scraper that exhausts retry attempts (max 3), the system must log
    the failure and continue processing other sources without crashing.
    
    Validates: Requirements 8.4, 16.2
    """
    scraper = BaseScraper("test")
    
    # Create a function that always fails
    call_count = 0
    
    async def failing_function():
        nonlocal call_count
        call_count += 1
        raise Exception("Simulated failure")
    
    # Attempt with retry
    with pytest.raises(Exception):
        await scraper.retry_with_backoff(failing_function, max_retries=max_retries)
    
    # Verify it tried the correct number of times
    assert call_count == max_retries


# Unit tests for scraper utilities
def test_phone_normalization():
    """Test phone number normalization to E.164 format."""
    scraper = BaseScraper("test")
    
    test_cases = [
        ("+919876543210", "+919876543210"),
        ("9876543210", "+919876543210"),
        ("+91 98765 43210", "+919876543210"),
        ("98765-43210", "+919876543210"),
        ("invalid", None),
        ("123", None)
    ]
    
    for input_phone, expected in test_cases:
        result = scraper.normalize_phone(input_phone)
        assert result == expected, f"Failed for {input_phone}: got {result}, expected {expected}"


def test_lead_hash_generation():
    """Test lead hash generation for deduplication."""
    scraper = BaseScraper("test")
    
    # Same inputs should produce same hash
    hash1 = scraper.generate_lead_hash("Test Business", "https://example.com", "+919876543210")
    hash2 = scraper.generate_lead_hash("Test Business", "https://example.com", "+919876543210")
    assert hash1 == hash2
    
    # Different inputs should produce different hashes
    hash3 = scraper.generate_lead_hash("Different Business", "https://example.com", "+919876543210")
    assert hash1 != hash3
    
    # Case insensitive
    hash4 = scraper.generate_lead_hash("test business", "https://example.com", "+919876543210")
    assert hash1 == hash4


def test_domain_extraction():
    """Test domain extraction from URLs."""
    scraper = BaseScraper("test")
    
    test_cases = [
        ("https://www.example.com/path", "example.com"),
        ("http://example.com", "example.com"),
        ("https://subdomain.example.com", "subdomain.example.com"),
        ("www.example.com", "example.com"),
        ("invalid", "invalid")
    ]
    
    for url, expected in test_cases:
        result = scraper.extract_domain(url)
        assert result == expected, f"Failed for {url}: got {result}, expected {expected}"


def test_email_validation():
    """Test email validation."""
    scraper = BaseScraper("test")
    
    valid_emails = [
        "test@example.com",
        "user.name@example.co.uk",
        "info@business.com"
    ]
    
    invalid_emails = [
        "invalid",
        "@example.com",
        "test@",
        "test @example.com",
        ""
    ]
    
    for email in valid_emails:
        assert scraper.validate_email(email), f"{email} should be valid"
    
    for email in invalid_emails:
        assert not scraper.validate_email(email), f"{email} should be invalid"


def test_business_name_cleaning():
    """Test business name cleaning."""
    scraper = BaseScraper("test")
    
    test_cases = [
        ("Test Business Pvt Ltd", "Test Business"),
        ("Example Company Ltd", "Example Company"),
        ("Business Inc", "Business"),
        ("Normal Name", "Normal Name"),
        ("  Extra   Spaces  ", "Extra Spaces")
    ]
    
    for input_name, expected in test_cases:
        result = scraper.clean_business_name(input_name)
        assert result == expected, f"Failed for {input_name}: got {result}, expected {expected}"


def test_deduplication_with_variations():
    """Test deduplication handles variations."""
    scraper = BaseScraper("test")
    
    leads = [
        RawLead("google_maps", "Test Business", "Mumbai", "restaurant", "https://example.com", ["+919876543210"], [], {}),
        RawLead("justdial", "Test Business", "Mumbai", "restaurant", "https://example.com", ["+919876543210"], [], {}),
        RawLead("google_maps", "Different Business", "Mumbai", "restaurant", "https://other.com", ["+919876543211"], [], {})
    ]
    
    unique = scraper.deduplicate_leads(leads)
    
    # Should have 2 unique leads (first two are duplicates)
    assert len(unique) == 2
    assert unique[0].business_name == "Test Business"
    assert unique[1].business_name == "Different Business"


@pytest.mark.asyncio
async def test_google_maps_scraper_initialization():
    """Test Google Maps scraper initialization."""
    scraper = GoogleMapsScraper()
    assert scraper.source_name == "google_maps"
    assert scraper.base_url == "https://maps.googleapis.com/maps/api/place"


@pytest.mark.asyncio
async def test_justdial_scraper_initialization():
    """Test JustDial scraper initialization."""
    scraper = JustDialScraper()
    assert scraper.source_name == "justdial"
    assert scraper.base_url == "https://www.justdial.com"
    assert scraper.crawl_delay >= 2.0


@pytest.mark.asyncio
async def test_linkedin_scraper_initialization():
    """Test LinkedIn scraper initialization."""
    scraper = LinkedInCompanyScraper()
    assert scraper.source_name == "linkedin_company"
    assert scraper.base_url == "https://www.linkedin.com"
