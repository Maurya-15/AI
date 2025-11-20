"""Property-based tests for voice call service."""

import pytest
from datetime import datetime, time, timedelta
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytz

from app.outreach.caller import VoiceCaller, CallResult, CallIntent, CallOutcome
from app.models import Lead, OptOut, OutreachHistory
from app.db import get_db_context


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def voice_caller():
    """Create voice caller instance."""
    return VoiceCaller()


@pytest.fixture
def sample_lead(test_db):
    """Create a sample lead for testing."""
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Restaurant",
            city="Mumbai",
            category="restaurant",
            primary_email="test@restaurant.com",
            primary_phone="+919876543210",
            email_verified=True,
            phone_verified=True,
            opted_out=False
        )
        db.add(lead)
        db.flush()
        return lead


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def phone_number(draw):
    """Generate valid phone numbers."""
    country_code = draw(st.sampled_from(["+91", "+1", "+44"]))
    number = draw(st.integers(min_value=1000000000, max_value=9999999999))
    return f"{country_code}{number}"


@st.composite
def business_lead(draw):
    """Generate business lead data."""
    return Lead(
        source="google_maps",
        business_name=draw(st.text(min_size=5, max_size=50)),
        city=draw(st.sampled_from(["Mumbai", "Delhi", "Bangalore"])),
        category=draw(st.sampled_from(["restaurant", "retail", "services"])),
        primary_phone=draw(phone_number()),
        phone_verified=True,
        opted_out=False
    )


# ============================================================================
# Property Tests
# ============================================================================

@settings(max_examples=100)
@given(lead=business_lead())
@pytest.mark.asyncio
async def test_property_37_call_initiation(lead, voice_caller, test_db):
    """
    Feature: devsync-sales-ai, Property 37: Call initiation
    For any voice call initiated, the system must use the configured telephony
    provider (Twilio or Exotel) to place the call to the verified phone number.
    Validates: Requirements 11.1
    """
    # Save lead to database
    with get_db_context() as db:
        db.add(lead)
        db.flush()
        lead_id = lead.id
    
    # Mock Twilio client
    with patch.object(voice_caller, '_get_twilio_client') as mock_client:
        mock_call = Mock()
        mock_call.sid = "CA1234567890"
        mock_client.return_value.calls.create.return_value = mock_call
        
        # Mock call window check to always return True
        with patch.object(voice_caller, 'is_in_call_window', return_value=True):
            # Initiate call
            result = await voice_caller.initiate_call(lead)
            
            # Verify Twilio was called
            if not voice_caller.config.DRY_RUN_MODE:
                mock_client.return_value.calls.create.assert_called_once()
                call_args = mock_client.return_value.calls.create.call_args
                
                # Verify correct phone number was used
                assert call_args.kwargs['to'] == lead.primary_phone
                assert call_args.kwargs['from_'] == voice_caller.config.TWILIO_PHONE_NUMBER
            
            # Verify result
            assert result.call_sid is not None


@settings(max_examples=100)
@given(
    business_name=st.text(min_size=5, max_size=50),
    category=st.sampled_from(["restaurant", "retail", "services", "manufacturing"])
)
@pytest.mark.asyncio
async def test_property_38_tts_introduction(business_name, category, voice_caller):
    """
    Feature: devsync-sales-ai, Property 38: TTS introduction
    For any call that is answered, the system must play a TTS message identifying
    the caller as DevSync Innovation and stating the call purpose.
    Validates: Requirements 11.2
    """
    # Create lead
    lead = Lead(
        source="google_maps",
        business_name=business_name,
        category=category,
        primary_phone="+919876543210"
    )
    
    # Generate TTS introduction
    intro = voice_caller.generate_tts_introduction(lead)
    
    # Verify required elements
    assert voice_caller.config.EMAIL_FROM_NAME in intro, "Must identify caller"
    assert category in intro, "Must mention business category"
    assert "website" in intro.lower(), "Must state purpose"
    
    # Verify it's a question/request
    assert "?" in intro or "please" in intro.lower(), "Must be polite/questioning"


@settings(max_examples=100)
@given(call_sid=st.text(min_size=10, max_size=20))
@pytest.mark.asyncio
async def test_property_39_voicemail_handling(call_sid, voice_caller, test_db):
    """
    Feature: devsync-sales-ai, Property 39: Voicemail handling
    For any call where voicemail is detected, the system must leave a pre-recorded
    message and mark the lead with a cooldown period (default 7 days).
    Validates: Requirements 11.4
    """
    # Create lead
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_phone="+919876543210",
            phone_verified=True
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
        
        # Create call history
        history = OutreachHistory(
            lead_id=lead_id,
            outreach_type="call",
            status="in-progress",
            provider_message_id=call_sid,
            attempted_at=datetime.utcnow()
        )
        db.add(history)
        db.flush()
    
    # Handle voicemail
    await voice_caller.handle_voicemail(call_sid, lead_id)
    
    # Verify outcome was set to voicemail
    with get_db_context() as db:
        history = db.query(OutreachHistory).filter(
            OutreachHistory.provider_message_id == call_sid
        ).first()
        
        assert history is not None, "History record must exist"
        assert history.outcome == "voicemail", "Outcome must be set to voicemail"
        assert history.completed_at is not None, "Completion time must be set"
        
        # Verify lead was updated
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        assert lead.last_contacted_at is not None, "Last contact time must be updated"
        assert lead.contact_count > 0, "Contact count must be incremented"


@settings(max_examples=100)
@given(
    call_sid=st.text(min_size=10, max_size=20),
    duration=st.integers(min_value=0, max_value=300),
    status=st.sampled_from(["completed", "busy", "no-answer", "failed"])
)
@pytest.mark.asyncio
async def test_property_40_call_logging(call_sid, duration, status, voice_caller, test_db):
    """
    Feature: devsync-sales-ai, Property 40: Call logging
    For any completed call, the system must store the call outcome, duration,
    transcript (if available), and recording reference to the database.
    Validates: Requirements 11.5
    """
    # Create lead and call history
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_phone="+919876543210",
            phone_verified=True
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
        
        history = OutreachHistory(
            lead_id=lead_id,
            outreach_type="call",
            status="initiated",
            provider_message_id=call_sid,
            attempted_at=datetime.utcnow()
        )
        db.add(history)
        db.flush()
    
    # Handle call status
    recording_url = f"https://api.twilio.com/recordings/{call_sid}"
    await voice_caller.handle_call_status(call_sid, status, duration, recording_url)
    
    # Verify logging
    with get_db_context() as db:
        history = db.query(OutreachHistory).filter(
            OutreachHistory.provider_message_id == call_sid
        ).first()
        
        assert history is not None, "History record must exist"
        assert history.status == status, "Status must be updated"
        assert history.duration_seconds == duration, "Duration must be stored"
        assert history.recording_url == recording_url, "Recording URL must be stored"
        assert history.completed_at is not None, "Completion time must be set"
        assert history.outcome is not None, "Outcome must be determined"


@settings(max_examples=100)
@given(phone=phone_number())
@pytest.mark.asyncio
async def test_property_25_dnc_list_checking(phone, voice_caller, test_db):
    """
    Feature: devsync-sales-ai, Property 25: DNC list checking
    For any phone number that appears on the configured Do Not Call registry,
    the system must skip the contact and not place a call.
    Validates: Requirements 6.4
    """
    # Add phone to DNC registry
    voice_caller._dnc_registry.add(phone)
    
    # Check DNC registry
    is_on_dnc = await voice_caller.check_dnc_registry(phone)
    
    # Must be detected
    assert is_on_dnc, "Phone on DNC registry must be detected"
    
    # Create lead with DNC phone
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_phone=phone,
            phone_verified=True
        )
        db.add(lead)
        db.flush()
    
    # Try to initiate call
    with patch.object(voice_caller, '_get_twilio_client') as mock_client:
        result = await voice_caller.initiate_call(lead)
        
        # Call should be blocked
        assert not result.status == "initiated", "Call to DNC number must be blocked"
        assert result.error is not None, "Error must be set"
        assert "dnc" in result.error.lower(), "Error must mention DNC"
        
        # Twilio should not be called
        mock_client.return_value.calls.create.assert_not_called()


# ============================================================================
# Unit Tests for Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_call_window_enforcement_weekday(voice_caller):
    """Test that calls are only allowed on weekdays."""
    # Monday (weekday)
    monday = datetime(2024, 1, 1, 12, 0)  # Monday at noon
    assert voice_caller.is_in_call_window(monday), "Monday should be allowed"
    
    # Saturday (weekend)
    saturday = datetime(2024, 1, 6, 12, 0)  # Saturday at noon
    assert not voice_caller.is_in_call_window(saturday), "Saturday should not be allowed"
    
    # Sunday (weekend)
    sunday = datetime(2024, 1, 7, 12, 0)  # Sunday at noon
    assert not voice_caller.is_in_call_window(sunday), "Sunday should not be allowed"


@pytest.mark.asyncio
async def test_call_window_enforcement_time(voice_caller):
    """Test that calls are only allowed during call window hours."""
    # Before window (10:00 AM)
    before = datetime(2024, 1, 1, 10, 0)
    assert not voice_caller.is_in_call_window(before), "Before window should not be allowed"
    
    # Start of window (11:00 AM)
    start = datetime(2024, 1, 1, 11, 0)
    assert voice_caller.is_in_call_window(start), "Start of window should be allowed"
    
    # Middle of window (2:00 PM)
    middle = datetime(2024, 1, 1, 14, 0)
    assert voice_caller.is_in_call_window(middle), "Middle of window should be allowed"
    
    # End of window (5:00 PM)
    end = datetime(2024, 1, 1, 17, 0)
    assert voice_caller.is_in_call_window(end), "End of window should be allowed"
    
    # After window (6:00 PM)
    after = datetime(2024, 1, 1, 18, 0)
    assert not voice_caller.is_in_call_window(after), "After window should not be allowed"


@pytest.mark.asyncio
async def test_intent_detection_interested(voice_caller):
    """Test intent detection for interested responses."""
    transcripts = [
        "Yes, I'm interested",
        "Tell me more",
        "Sounds good",
        "Okay, yes"
    ]
    
    for transcript in transcripts:
        intent = voice_caller.detect_intent(transcript)
        assert intent == CallIntent.INTERESTED, f"Should detect interested in: {transcript}"


@pytest.mark.asyncio
async def test_intent_detection_remove(voice_caller):
    """Test intent detection for remove requests."""
    transcripts = [
        "Remove me from your list",
        "Stop calling",
        "Do not call me again",
        "I want to unsubscribe"
    ]
    
    for transcript in transcripts:
        intent = voice_caller.detect_intent(transcript)
        assert intent == CallIntent.REMOVE, f"Should detect remove in: {transcript}"


@pytest.mark.asyncio
async def test_intent_detection_not_interested(voice_caller):
    """Test intent detection for not interested responses."""
    transcripts = [
        "No thanks",
        "Not interested",
        "No, not now"
    ]
    
    for transcript in transcripts:
        intent = voice_caller.detect_intent(transcript)
        assert intent == CallIntent.NOT_INTERESTED, f"Should detect not interested in: {transcript}"


@pytest.mark.asyncio
async def test_opted_out_phone_blocked(voice_caller, test_db):
    """Test that opted-out phones are blocked."""
    phone = "+919876543210"
    
    # Create opt-out record
    with get_db_context() as db:
        opt_out = OptOut(
            contact_type="phone",
            contact_value=phone,
            opt_out_method="call_request",
            opted_out_at=datetime.utcnow()
        )
        db.add(opt_out)
    
    # Check opt-out
    is_opted_out = await voice_caller.check_opt_out(phone)
    assert is_opted_out, "Opted-out phone must be detected"
    
    # Try to call
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_phone=phone,
            phone_verified=True,
            opted_out=True
        )
        db.add(lead)
        db.flush()
    
    with patch.object(voice_caller, '_get_twilio_client') as mock_client:
        result = await voice_caller.initiate_call(lead)
        
        # Should be blocked
        assert result.status == "failed", "Call to opted-out phone must fail"
        assert "opted out" in result.error.lower(), "Error must mention opt-out"


@pytest.mark.asyncio
async def test_dry_run_mode_no_actual_call(voice_caller, test_db):
    """Test that dry-run mode doesn't actually place calls."""
    # Enable dry-run mode
    original_dry_run = voice_caller.config.DRY_RUN_MODE
    voice_caller.config.DRY_RUN_MODE = True
    
    try:
        with get_db_context() as db:
            lead = Lead(
                source="google_maps",
                business_name="Test Business",
                primary_phone="+919876543210",
                phone_verified=True
            )
            db.add(lead)
            db.flush()
        
        with patch.object(voice_caller, '_get_twilio_client') as mock_client:
            result = await voice_caller.initiate_call(lead)
            
            # Should succeed but not actually call
            assert result.status == "completed", "Dry-run should succeed"
            assert result.outcome == "dry-run", "Outcome should be dry-run"
            assert "dry-run" in result.call_sid, "Call SID should indicate dry-run"
            
            # Twilio should not be called
            mock_client.assert_not_called()
    
    finally:
        voice_caller.config.DRY_RUN_MODE = original_dry_run


@pytest.mark.asyncio
async def test_twiml_generation_with_intent(voice_caller, test_db):
    """Test TwiML generation for different intents."""
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            category="restaurant",
            primary_phone="+919876543210"
        )
        db.add(lead)
        db.flush()
    
    # Test different intents
    intents = [
        CallIntent.INTERESTED,
        CallIntent.NOT_INTERESTED,
        CallIntent.REMOVE,
        CallIntent.CALL_BACK
    ]
    
    for intent in intents:
        twiml = voice_caller.generate_twiml_response(lead, intent)
        
        # Should generate valid TwiML
        assert twiml is not None, f"TwiML should be generated for {intent}"
        assert len(twiml) > 0, f"TwiML should not be empty for {intent}"
        assert "<Response>" in twiml, "TwiML should contain Response tag"


@pytest.mark.asyncio
async def test_call_response_with_remove_intent(voice_caller, test_db):
    """Test that remove intent triggers opt-out."""
    call_sid = "CA1234567890"
    transcript = "Please remove me from your calling list"
    
    with get_db_context() as db:
        lead = Lead(
            source="google_maps",
            business_name="Test Business",
            primary_phone="+919876543210",
            phone_verified=True,
            opted_out=False
        )
        db.add(lead)
        db.flush()
        lead_id = lead.id
        
        history = OutreachHistory(
            lead_id=lead_id,
            outreach_type="call",
            status="in-progress",
            provider_message_id=call_sid,
            attempted_at=datetime.utcnow()
        )
        db.add(history)
        db.flush()
    
    # Handle call response
    await voice_caller.handle_call_response(call_sid, transcript, lead_id)
    
    # Verify opt-out was triggered
    with get_db_context() as db:
        opt_out = db.query(OptOut).filter(
            OptOut.contact_type == "phone",
            OptOut.contact_value == "+919876543210"
        ).first()
        
        assert opt_out is not None, "Opt-out should be created for remove intent"


@pytest.mark.asyncio
async def test_empty_transcript_intent_detection(voice_caller):
    """Test intent detection with empty transcript."""
    intent = voice_caller.detect_intent("")
    assert intent == CallIntent.UNKNOWN, "Empty transcript should return UNKNOWN"
    
    intent_none = voice_caller.detect_intent(None)
    assert intent_none == CallIntent.UNKNOWN, "None transcript should return UNKNOWN"
