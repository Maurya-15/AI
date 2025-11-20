"""Voice call service with Vonage and Twilio integration."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, time, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio

from app.config import get_settings
from app.db import get_db_context
from app.models import OutreachHistory, Lead, OptOut
from app.audit import AuditLogger

logger = logging.getLogger(__name__)

# Import vonage at module level
try:
    import vonage
except ImportError:
    vonage = None


class CallStatus(str, Enum):
    """Call status enum."""
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no-answer"


class CallOutcome(str, Enum):
    """Call outcome enum."""
    ANSWERED = "answered"
    VOICEMAIL = "voicemail"
    BUSY = "busy"
    NO_ANSWER = "no-answer"
    FAILED = "failed"


class CallIntent(str, Enum):
    """Detected intent from call."""
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    REMOVE = "remove"
    CALL_BACK = "call_back"
    TALK_TO_HUMAN = "talk_to_human"
    UNKNOWN = "unknown"


@dataclass
class CallResult:
    """Call result data structure."""
    call_sid: str
    status: str
    duration: Optional[int] = None
    outcome: Optional[str] = None
    transcript: Optional[str] = None
    recording_url: Optional[str] = None
    intent: Optional[str] = None
    error: Optional[str] = None


class VoiceCaller:
    """Voice call service with Twilio integration."""
    
    # Weekdays only (Monday=0, Sunday=6)
    ALLOWED_WEEKDAYS = [0, 1, 2, 3, 4]  # Monday-Friday
    
    # Intent detection keywords
    INTENT_KEYWORDS = {
        CallIntent.INTERESTED: ["yes", "interested", "tell me more", "sounds good", "okay"],
        CallIntent.NOT_INTERESTED: ["no", "not interested", "no thanks", "not now"],
        CallIntent.REMOVE: ["remove", "stop", "do not call", "don't call", "unsubscribe"],
        CallIntent.CALL_BACK: ["call back", "later", "another time", "busy now"],
        CallIntent.TALK_TO_HUMAN: ["human", "person", "representative", "agent", "speak to someone"]
    }
    
    def __init__(self):
        """Initialize voice caller."""
        self.config = get_settings()
        self.audit = AuditLogger()
        self._twilio_client = None
        self._vonage_client = None
        self._dnc_registry = set()  # Do Not Call registry
        
        # Determine which provider to use
        self.provider = self._determine_provider()
        
        # Load DNC registry if configured
        if self.config.DNC_REGISTRY_FILE:
            self._load_dnc_registry()
    
    def _determine_provider(self) -> str:
        """Determine which telephony provider to use."""
        if self.config.VONAGE_API_KEY and self.config.VONAGE_API_SECRET:
            return "vonage"
        elif self.config.TWILIO_ACCOUNT_SID and self.config.TWILIO_AUTH_TOKEN:
            return "twilio"
        else:
            return "none"
    
    def _load_dnc_registry(self):
        """Load Do Not Call registry from file."""
        try:
            import os
            if os.path.exists(self.config.DNC_REGISTRY_FILE):
                with open(self.config.DNC_REGISTRY_FILE, 'r') as f:
                    for line in f:
                        phone = line.strip()
                        if phone:
                            self._dnc_registry.add(phone)
                logger.info(f"Loaded {len(self._dnc_registry)} numbers from DNC registry")
        except Exception as e:
            logger.error(f"Error loading DNC registry: {e}")
    
    def _get_vonage_client(self):
        """Get or create Vonage client."""
        if self._vonage_client is None:
            try:
                from vonage import Auth, Vonage
                self._vonage_client = Vonage(
                    Auth(
                        api_key=self.config.VONAGE_API_KEY,
                        api_secret=self.config.VONAGE_API_SECRET
                    )
                )
            except Exception as e:
                logger.error(f"Error creating Vonage client: {e}")
                raise ValueError("Vonage credentials not configured")
        return self._vonage_client
    
    def _get_twilio_client(self):
        """Get or create Twilio client."""
        if self._twilio_client is None:
            try:
                from twilio.rest import Client
                self._twilio_client = Client(
                    self.config.TWILIO_ACCOUNT_SID,
                    self.config.TWILIO_AUTH_TOKEN
                )
            except Exception as e:
                logger.error(f"Error creating Twilio client: {e}")
                raise ValueError("Twilio credentials not configured")
        return self._twilio_client
    
    def is_in_call_window(self, check_time: Optional[datetime] = None) -> bool:
        """
        Check if current time is within call window.
        
        Args:
            check_time: Time to check (defaults to now in IST)
            
        Returns:
            True if within call window, False otherwise
        """
        if check_time is None:
            import pytz
            ist = pytz.timezone(self.config.TIMEZONE)
            check_time = datetime.now(ist)
        
        # Check weekday
        if check_time.weekday() not in self.ALLOWED_WEEKDAYS:
            return False
        
        # Parse call window times from config
        try:
            start_hour, start_min = map(int, self.config.CALL_WINDOW_START.split(':'))
            end_hour, end_min = map(int, self.config.CALL_WINDOW_END.split(':'))
            window_start = time(start_hour, start_min)
            window_end = time(end_hour, end_min)
        except Exception as e:
            logger.error(f"Error parsing call window times: {e}")
            # Fallback to default 11 AM - 5 PM
            window_start = time(11, 0)
            window_end = time(17, 0)
        
        # Check time window
        current_time = check_time.time()
        return window_start <= current_time <= window_end
    
    async def check_dnc_registry(self, phone: str) -> bool:
        """
        Check if phone number is on Do Not Call registry.
        
        Args:
            phone: Phone number to check
            
        Returns:
            True if on DNC registry, False otherwise
        """
        return phone in self._dnc_registry
    
    async def check_opt_out(self, phone: str) -> bool:
        """
        Check if phone is opted out.
        
        Args:
            phone: Phone number to check
            
        Returns:
            True if opted out, False otherwise
        """
        try:
            with get_db_context() as db:
                opt_out = db.query(OptOut).filter(
                    OptOut.contact_type == "phone",
                    OptOut.contact_value == phone
                ).first()
                return opt_out is not None
        except Exception as e:
            logger.error(f"Error checking opt-out: {e}")
            return True  # Fail safe
    
    def detect_intent(self, transcript: str) -> CallIntent:
        """
        Detect caller intent from transcript.
        
        Args:
            transcript: Call transcript text
            
        Returns:
            Detected intent
        """
        if not transcript:
            return CallIntent.UNKNOWN
        
        transcript_lower = transcript.lower()
        
        # Check each intent's keywords
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in transcript_lower:
                    return intent
        
        return CallIntent.UNKNOWN
    
    def generate_tts_introduction(self, lead: Lead) -> str:
        """
        Generate TTS introduction message.
        
        Args:
            lead: Lead being called
            
        Returns:
            TTS message text
        """
        business_name = lead.business_name or "there"
        category = lead.category or "business"
        
        message = (
            f"Hello, this is calling from {self.config.EMAIL_FROM_NAME}. "
            f"We build websites for {category} businesses. "
            f"May I speak with the person who manages your website? "
            f"Please say yes if you're interested, or say remove to opt out."
        )
        
        return message
    
    async def initiate_call(
        self,
        lead: Lead,
        campaign_id: Optional[int] = None
    ) -> CallResult:
        """
        Initiate voice call to lead.
        
        Args:
            lead: Lead to call
            campaign_id: Optional campaign ID
            
        Returns:
            CallResult with call details
        """
        phone = lead.primary_phone
        
        # Check if dry-run mode
        if self.config.DRY_RUN_MODE:
            logger.info(f"[DRY-RUN] Would call {phone} for lead {lead.id}")
            await self.audit.log_outreach(
                lead.id,
                "call",
                {"status": "dry-run", "phone": phone}
            )
            return CallResult(
                call_sid=f"dry-run-{lead.id}",
                status="completed",
                outcome="dry-run"
            )
        
        # Check call window
        if not self.is_in_call_window():
            logger.warning(f"Outside call window, skipping call to {phone}")
            return CallResult(
                call_sid="",
                status="failed",
                error="Outside call window"
            )
        
        # Check DNC registry
        if await self.check_dnc_registry(phone):
            logger.warning(f"Phone {phone} is on DNC registry, skipping")
            return CallResult(
                call_sid="",
                status="failed",
                error="On DNC registry"
            )
        
        # Check opt-out
        if await self.check_opt_out(phone):
            logger.warning(f"Phone {phone} is opted out, skipping")
            return CallResult(
                call_sid="",
                status="failed",
                error="Opted out"
            )
        
        # Initiate call via configured provider
        try:
            if self.provider == "vonage":
                return await self._initiate_vonage_call(lead, phone, campaign_id)
            elif self.provider == "twilio":
                return await self._initiate_twilio_call(lead, phone, campaign_id)
            else:
                logger.error("No telephony provider configured")
                return CallResult(
                    call_sid="",
                    status="failed",
                    error="No telephony provider configured"
                )
            
        except Exception as e:
            logger.error(f"Error initiating call: {e}")
            await self.audit.log_error(
                component="caller",
                error=e,
                context={"lead_id": lead.id, "phone": phone}
            )
            return CallResult(
                call_sid="",
                status="failed",
                error=str(e)
            )
    
    async def _initiate_vonage_call(self, lead, phone: str, campaign_id: Optional[int]) -> CallResult:
        """Initiate call via Vonage."""
        try:
            client = self._get_vonage_client()
            
            # Generate TTS message
            intro_message = self.generate_tts_introduction(lead)
            
            # Create call using Vonage Voice API
            response = client.voice.create_call({
                'to': [{'type': 'phone', 'number': phone}],
                'from': {'type': 'phone', 'number': self.config.VONAGE_PHONE_NUMBER},
                'ncco': [
                    {
                        'action': 'talk',
                        'text': intro_message,
                        'voiceName': 'Aditi'
                    },
                    {
                        'action': 'input',
                        'eventUrl': [f'https://devsyncinnovation.com/call/response?lead_id={lead.id}'],
                        'type': ['speech'],
                        'speech': {
                            'endOnSilence': 3,
                            'language': 'en-IN'
                        }
                    }
                ]
            })
            
            call_uuid = response.get('uuid', f'vonage-{lead.id}')
            logger.info(f"Initiated Vonage call {call_uuid} to {phone}")
            
            # Store in database
            await self._persist_call(lead.id, call_uuid, campaign_id)
            
            # Audit log
            await self.audit.log_outreach(
                lead.id,
                "call",
                {
                    "status": "initiated",
                    "call_sid": call_uuid,
                    "phone": phone,
                    "provider": "vonage"
                }
            )
            
            return CallResult(
                call_sid=call_uuid,
                status="initiated"
            )
            
        except Exception as e:
            logger.error(f"Error initiating Vonage call: {e}")
            raise
    
    async def _initiate_twilio_call(self, lead, phone: str, campaign_id: Optional[int]) -> CallResult:
        """Initiate call via Twilio."""
        try:
            client = self._get_twilio_client()
            
            # Generate TwiML URL for call flow
            twiml_url = f"https://devsyncinnovation.com/call/flow?lead_id={lead.id}"
            
            call = client.calls.create(
                to=phone,
                from_=self.config.TWILIO_PHONE_NUMBER,
                url=twiml_url,
                status_callback=f"https://devsyncinnovation.com/call/status",
                machine_detection="DetectMessageEnd",
                timeout=30
            )
            
            logger.info(f"Initiated Twilio call {call.sid} to {phone}")
            
            # Store in database
            await self._persist_call(lead.id, call.sid, campaign_id)
            
            # Audit log
            await self.audit.log_outreach(
                lead.id,
                "call",
                {
                    "status": "initiated",
                    "call_sid": call.sid,
                    "phone": phone,
                    "provider": "twilio"
                }
            )
            
            return CallResult(
                call_sid=call.sid,
                status="initiated"
            )
            
        except Exception as e:
            logger.error(f"Error initiating Twilio call: {e}")
            raise
    
    async def _persist_call(
        self,
        lead_id: int,
        call_sid: str,
        campaign_id: Optional[int] = None
    ):
        """Persist call record to database."""
        try:
            with get_db_context() as db:
                history = OutreachHistory(
                    lead_id=lead_id,
                    campaign_id=campaign_id,
                    outreach_type="call",
                    status="initiated",
                    provider_message_id=call_sid,
                    attempted_at=datetime.utcnow()
                )
                db.add(history)
        except Exception as e:
            logger.error(f"Error persisting call: {e}")
    
    async def handle_call_status(
        self,
        call_sid: str,
        status: str,
        duration: Optional[int] = None,
        recording_url: Optional[str] = None
    ):
        """
        Handle call status callback from Twilio.
        
        Args:
            call_sid: Twilio call SID
            status: Call status
            duration: Call duration in seconds
            recording_url: URL to call recording
        """
        try:
            logger.info(f"Call {call_sid} status: {status}")
            
            # Update database
            with get_db_context() as db:
                history = db.query(OutreachHistory).filter(
                    OutreachHistory.provider_message_id == call_sid
                ).first()
                
                if history:
                    history.status = status
                    history.duration_seconds = duration
                    history.recording_url = recording_url
                    history.completed_at = datetime.utcnow()
                    
                    # Determine outcome
                    if status == "completed":
                        history.outcome = "answered"
                    elif status == "busy":
                        history.outcome = "busy"
                    elif status == "no-answer":
                        history.outcome = "no-answer"
                    elif status == "failed":
                        history.outcome = "failed"
                    
                    # Update lead
                    lead = db.query(Lead).filter(Lead.id == history.lead_id).first()
                    if lead:
                        lead.last_contacted_at = datetime.utcnow()
                        lead.contact_count += 1
            
            await self.audit.log_api_call(
                "twilio",
                "call_status",
                {"call_sid": call_sid, "status": status, "duration": duration}
            )
            
        except Exception as e:
            logger.error(f"Error handling call status: {e}")
    
    async def handle_voicemail(
        self,
        call_sid: str,
        lead_id: int
    ):
        """
        Handle voicemail detection.
        
        Args:
            call_sid: Twilio call SID
            lead_id: Lead ID
        """
        try:
            logger.info(f"Voicemail detected for call {call_sid}")
            
            # Update database
            with get_db_context() as db:
                history = db.query(OutreachHistory).filter(
                    OutreachHistory.provider_message_id == call_sid
                ).first()
                
                if history:
                    history.outcome = "voicemail"
                    history.completed_at = datetime.utcnow()
                
                # Update lead - don't call again for 7 days
                lead = db.query(Lead).filter(Lead.id == lead_id).first()
                if lead:
                    lead.last_contacted_at = datetime.utcnow()
                    lead.contact_count += 1
            
            logger.info(f"Marked lead {lead_id} for 7-day cooldown after voicemail")
            
        except Exception as e:
            logger.error(f"Error handling voicemail: {e}")
    
    async def handle_call_response(
        self,
        call_sid: str,
        transcript: str,
        lead_id: int
    ):
        """
        Handle call response and detect intent.
        
        Args:
            call_sid: Twilio call SID
            transcript: Speech recognition transcript
            lead_id: Lead ID
        """
        try:
            # Detect intent
            intent = self.detect_intent(transcript)
            
            logger.info(f"Call {call_sid} intent: {intent}")
            
            # Update database
            with get_db_context() as db:
                history = db.query(OutreachHistory).filter(
                    OutreachHistory.provider_message_id == call_sid
                ).first()
                
                if history:
                    history.transcript = transcript
                    history.provider_response = {"intent": intent.value}
            
            # Handle remove request
            if intent == CallIntent.REMOVE:
                from app.opt_out import get_opt_out_manager
                opt_out_mgr = get_opt_out_manager()
                
                lead = None
                with get_db_context() as db:
                    lead = db.query(Lead).filter(Lead.id == lead_id).first()
                
                if lead and lead.primary_phone:
                    await opt_out_mgr.handle_call_opt_out(lead.primary_phone)
                    logger.info(f"Added phone {lead.primary_phone} to opt-out list")
            
            await self.audit.log_api_call(
                "twilio",
                "call_response",
                {
                    "call_sid": call_sid,
                    "intent": intent.value,
                    "transcript": transcript[:100]  # First 100 chars
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling call response: {e}")
    
    def generate_twiml_response(
        self,
        lead: Lead,
        intent: Optional[CallIntent] = None
    ) -> str:
        """
        Generate TwiML response for call flow.
        
        Args:
            lead: Lead being called
            intent: Detected intent (if any)
            
        Returns:
            TwiML XML string
        """
        from twilio.twiml.voice_response import VoiceResponse, Gather
        
        response = VoiceResponse()
        
        if intent is None:
            # Initial greeting
            intro = self.generate_tts_introduction(lead)
            
            gather = Gather(
                input='speech',
                timeout=5,
                action=f'/call/response?lead_id={lead.id}',
                speech_timeout='auto'
            )
            gather.say(intro, voice='Polly.Aditi')
            response.append(gather)
            
            # If no response
            response.say("Thank you. We'll follow up by email. Goodbye.", voice='Polly.Aditi')
            
        elif intent == CallIntent.INTERESTED:
            response.say(
                "Great! We'll send you more information by email. Thank you for your time.",
                voice='Polly.Aditi'
            )
            
        elif intent == CallIntent.NOT_INTERESTED:
            response.say(
                "No problem. Thank you for your time. Goodbye.",
                voice='Polly.Aditi'
            )
            
        elif intent == CallIntent.REMOVE:
            response.say(
                "You have been removed from our calling list. We apologize for any inconvenience. Goodbye.",
                voice='Polly.Aditi'
            )
            
        elif intent == CallIntent.CALL_BACK:
            response.say(
                "We'll call back at a better time. Thank you. Goodbye.",
                voice='Polly.Aditi'
            )
            
        elif intent == CallIntent.TALK_TO_HUMAN:
            response.say(
                "We'll have someone from our team reach out to you. Thank you. Goodbye.",
                voice='Polly.Aditi'
            )
        
        return str(response)
    
    async def get_call_history(
        self,
        lead_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        limit: int = 100
    ) -> list:
        """
        Get call history with optional filters.
        
        Args:
            lead_id: Filter by lead ID
            campaign_id: Filter by campaign ID
            limit: Maximum records to return
            
        Returns:
            List of call history records
        """
        try:
            with get_db_context() as db:
                query = db.query(OutreachHistory).filter(
                    OutreachHistory.outreach_type == "call"
                )
                
                if lead_id:
                    query = query.filter(OutreachHistory.lead_id == lead_id)
                if campaign_id:
                    query = query.filter(OutreachHistory.campaign_id == campaign_id)
                
                return query.order_by(OutreachHistory.attempted_at.desc()).limit(limit).all()
                
        except Exception as e:
            logger.error(f"Error retrieving call history: {e}")
            return []


# Global voice caller instance
_voice_caller: Optional[VoiceCaller] = None


def get_voice_caller() -> VoiceCaller:
    """Get or create global voice caller instance."""
    global _voice_caller
    if _voice_caller is None:
        _voice_caller = VoiceCaller()
    return _voice_caller
