# Design Document

## Overview

DevSyncSalesAI is a production-ready, compliance-focused business outreach automation platform built with Python 3.10+ and FastAPI. The system architecture follows a modular, service-oriented design with clear separation of concerns across scraping, verification, personalization, outreach, and monitoring components.

The system operates on a daily scheduled batch processing model where leads are scraped, verified, personalized, queued for approval (if enabled), and then contacted via email and voice calls within configured time windows and rate limits. All operations are logged for audit purposes, and the system enforces strict compliance with commercial communication regulations.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Operator Dashboard                       │
│                    (React SPA - Approval & Monitoring)           │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API
┌────────────────────────────┴────────────────────────────────────┐
│                         FastAPI Backend                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Scraper    │  │  Verifier    │  │  Outreach    │          │
│  │   Service    │  │   Service    │  │   Service    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Scheduler   │  │    Queue     │  │    Audit     │          │
│  │   Service    │  │   Manager    │  │   Logger     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                    PostgreSQL Database                           │
│  Tables: leads, outreach_history, opt_outs,                     │
│          verification_results, audit_logs, campaigns             │
└──────────────────────────────────────────────────────────────────┘

External Services:
├─ Google Maps Places API (Lead Scraping)
├─ JustDial / IndiaMART (Lead Scraping)
├─ AbstractAPI / ZeroBounce (Email Verification)
├─ Twilio Lookup / NumVerify (Phone Verification)
├─ OpenAI / AIMLAPI (Email Personalization)
├─ SendGrid / Mailgun (Email Delivery)
├─ Twilio Voice / Exotel (Voice Calls)
└─ ElevenLabs (TTS for Calls)
```

### Technology Stack

- **Backend Framework**: FastAPI 0.104+ (async support, automatic OpenAPI docs)
- **Database**: PostgreSQL 14+ with SQLAlchemy 2.0 ORM
- **Task Scheduling**: APScheduler 3.10+ for cron-like job execution
- **Queue Management**: Database-backed queue with Redis as optional enhancement
- **API Clients**: httpx for async HTTP requests, official SDKs where available
- **Frontend**: React 18+ with Vite, TailwindCSS for styling
- **Deployment**: Docker containers, Render.com compatible
- **Monitoring**: Structured logging with Python logging module, optional Sentry integration

### Design Principles

1. **Fail-Safe Defaults**: System starts in dry-run mode with approval required
2. **Explicit Over Implicit**: All configuration via environment variables, no hidden defaults
3. **Audit Everything**: Every action logged with timestamp, actor, and outcome
4. **Graceful Degradation**: Continue processing on individual failures, alert on systemic issues
5. **Compliance by Design**: Opt-out checks and rate limits enforced at the code level, not configuration

## Components and Interfaces

### 1. Scraper Service

**Purpose**: Extract business contact information from approved public sources.

**Modules**:
- `scraper/base.py`: Abstract base class defining scraper interface
- `scraper/google_maps.py`: Google Maps Places API adapter
- `scraper/justdial.py`: JustDial HTML scraper with rate limiting
- `scraper/linkedin_company.py`: LinkedIn Company page scraper

**Interface**:
```python
class BaseScraper(ABC):
    @abstractmethod
    async def scrape(self, query: ScrapeQuery) -> List[RawLead]:
        """Scrape leads based on query parameters."""
        pass
    
    @abstractmethod
    async def validate_source(self) -> bool:
        """Verify scraper can access the source."""
        pass

@dataclass
class ScrapeQuery:
    location: str
    category: str
    max_results: int = 50

@dataclass
class RawLead:
    source: str
    business_name: str
    city: str
    category: str
    website: Optional[str]
    phone_numbers: List[str]
    emails: List[str]
    raw_metadata: dict
```

**Key Behaviors**:
- Respect robots.txt for web scrapers
- Implement exponential backoff on 429/5xx responses (base delay 1s, max 60s)
- Deduplicate leads based on (business_name + website + primary_phone) hash
- Normalize phone numbers to E.164 format
- Extract emails from website contact pages if not directly available

### 2. Verifier Service

**Purpose**: Validate email deliverability and phone number validity.

**Modules**:
- `verifier/email_verify.py`: Email verification using AbstractAPI/ZeroBounce/Hunter
- `verifier/phone_verify.py`: Phone verification using Twilio Lookup/NumVerify

**Interface**:
```python
class EmailVerifier:
    async def verify(self, email: str) -> EmailVerificationResult:
        """Verify email deliverability and type."""
        pass

class PhoneVerifier:
    async def verify(self, phone: str, country_code: str) -> PhoneVerificationResult:
        """Verify phone validity and carrier type."""
        pass

@dataclass
class EmailVerificationResult:
    email: str
    is_deliverable: bool
    is_business: bool  # False for gmail/yahoo/hotmail
    confidence_score: float  # 0.0 to 1.0
    provider_response: dict
    verified_at: datetime

@dataclass
class PhoneVerificationResult:
    phone: str
    is_valid: bool
    carrier_type: str  # landline, mobile, voip
    is_business_line: bool
    confidence_score: float
    provider_response: dict
    verified_at: datetime
```

**Key Behaviors**:
- Cache verification results for 30 days to avoid redundant API calls
- Reject personal email providers (gmail.com, yahoo.com, hotmail.com, outlook.com)
- Accept role-based emails (info@, contact@, sales@, support@)
- Minimum confidence threshold: 0.7 for emails, 0.6 for phones
- Retry verification on transient failures (max 3 attempts)

### 3. Personalization Service

**Purpose**: Generate personalized email content using AI.

**Module**: `outreach/personalizer.py`

**Interface**:
```python
class EmailPersonalizer:
    async def generate(self, lead: VerifiedLead) -> PersonalizedEmail:
        """Generate personalized email content for lead."""
        pass
    
    async def generate_with_fallback(self, lead: VerifiedLead) -> PersonalizedEmail:
        """Generate with template fallback on AI failure."""
        pass

@dataclass
class PersonalizedEmail:
    subject: str
    body_html: str
    body_text: str
    personalization_method: str  # 'ai' or 'template'
    generated_at: datetime
```

**AI Prompt Template**:
```
You are writing a brief, professional cold email for DevSync Innovation, 
a web development company in India.

Business Details:
- Name: {business_name}
- Category: {category}
- City: {city}

Write a 3-line email:
Line 1: Personalized hook referencing their business or industry
Line 2: Value proposition - "We build fast, SEO-ready websites for {category} businesses"
Line 3: Clear CTA with scheduling link

Keep it under 80 words. Be professional but friendly. No pushy sales language.
```

**Fallback Template**:
```
Subject: Website Solutions for {business_name}

Hi {business_name} team,

I noticed you're in the {category} business in {city}. We specialize in 
building fast, SEO-optimized websites for {category} companies.

Would you be open to a quick 15-minute call to discuss how we can help 
grow your online presence?

Book a time: [scheduling_link]

Best regards,
DevSync Innovation Team
```

**Key Behaviors**:
- Call OpenAI GPT-4 or AIMLAPI with 5-second timeout
- Fall back to template on timeout or API failure
- Validate generated content length (50-150 words)
- Append compliance footer (address, unsubscribe link)
- Store generated content before sending for audit

### 4. Email Outreach Service

**Purpose**: Send personalized emails through reputable providers.

**Module**: `outreach/emailer.py`

**Interface**:
```python
class EmailSender:
    async def send(self, email: OutreachEmail) -> SendResult:
        """Send email through configured provider."""
        pass
    
    async def handle_webhook(self, event: WebhookEvent) -> None:
        """Process bounce/complaint/unsubscribe webhooks."""
        pass

@dataclass
class OutreachEmail:
    lead_id: int
    to_email: str
    subject: str
    body_html: str
    body_text: str
    unsubscribe_token: str

@dataclass
class SendResult:
    success: bool
    message_id: Optional[str]
    error: Optional[str]
    provider_response: dict
    sent_at: datetime
```

**Provider Adapters**:
- SendGrid API (preferred for high deliverability)
- Mailgun API (alternative)
- SMTP with TLS (fallback, requires proper SPF/DKIM/DMARC)

**Key Behaviors**:
- Generate unique unsubscribe token per recipient (UUID4)
- Enforce per-domain throttling: max 5 emails/hour/domain
- Retry on transient failures: 3 attempts with exponential backoff (1s, 4s, 16s)
- Mark permanent failures (invalid recipient, blocked) as undeliverable
- Process webhooks to update opt-out status and delivery status
- Include required headers: List-Unsubscribe, Precedence: bulk

### 5. Voice Call Service

**Purpose**: Conduct automated voice calls with TTS and ASR.

**Module**: `outreach/caller.py`

**Interface**:
```python
class VoiceCaller:
    async def initiate_call(self, lead: VerifiedLead) -> CallResult:
        """Initiate voice call through telephony provider."""
        pass
    
    async def handle_call_status(self, call_sid: str, status: str) -> None:
        """Process call status callbacks."""
        pass

@dataclass
class CallResult:
    call_sid: str
    status: str  # initiated, ringing, in-progress, completed, failed
    duration: Optional[int]
    outcome: Optional[str]  # answered, voicemail, busy, no-answer
    transcript: Optional[str]
    recording_url: Optional[str]
```

**Call Flow (TwiML for Twilio)**:
```xml
<Response>
    <Say voice="Polly.Aditi">
        Hello, this is calling from DevSync Innovation. 
        We build websites for {category} businesses. 
        May I speak with the person who manages your website?
    </Say>
    <Gather input="speech" timeout="5" action="/call/response">
        <Say>Please say yes if you're interested, or say remove to opt out.</Say>
    </Gather>
    <Say>Thank you. We'll follow up by email. Goodbye.</Say>
</Response>
```

**Intent Detection**:
- "yes", "interested", "tell me more" → Mark as interested, schedule follow-up
- "no", "not interested" → Mark as not interested, cooldown 90 days
- "remove", "stop", "do not call" → Add to opt-out list immediately
- "call back", "later" → Schedule retry in 3 days
- Voicemail detected → Leave message, no retry for 7 days

**Key Behaviors**:
- Use Twilio Programmable Voice or Exotel API
- Detect voicemail using Twilio's answering machine detection
- Limit call duration to 2 minutes maximum
- Store transcripts and recordings (if consent obtained)
- Respect call window: 11:00-17:00 IST on weekdays only
- Check Do Not Call registry before dialing (if configured)

### 6. Scheduler Service

**Purpose**: Execute daily outreach campaigns on schedule.

**Module**: `scheduler.py`

**Interface**:
```python
class CampaignScheduler:
    def schedule_daily_email_campaign(self) -> None:
        """Schedule email campaign for configured time."""
        pass
    
    def schedule_daily_call_campaign(self) -> None:
        """Schedule call campaign for configured window."""
        pass
    
    async def execute_email_campaign(self) -> CampaignReport:
        """Execute email outreach campaign."""
        pass
    
    async def execute_call_campaign(self) -> CampaignReport:
        """Execute call outreach campaign."""
        pass

@dataclass
class CampaignReport:
    campaign_id: int
    total_attempted: int
    total_success: int
    total_failed: int
    errors: List[str]
    started_at: datetime
    completed_at: datetime
```

**Scheduling Configuration**:
- Email campaign: Daily at 10:00 IST (configurable via EMAIL_SEND_TIME)
- Call campaign: Daily 11:00-17:00 IST, distributed evenly (configurable via CALL_WINDOW_START/END)
- Use APScheduler with CronTrigger for reliability
- Persist campaign state to database for recovery on restart

**Campaign Execution Logic**:
```python
async def execute_email_campaign():
    # 1. Check if dry-run mode enabled
    if config.DRY_RUN_MODE:
        logger.info("Dry-run mode: simulating email campaign")
    
    # 2. Get daily cap and already sent count
    daily_cap = config.DAILY_EMAIL_CAP
    sent_today = await get_emails_sent_today()
    remaining = daily_cap - sent_today
    
    if remaining <= 0:
        logger.info("Daily email cap reached")
        return
    
    # 3. Query verified, non-opted-out leads
    leads = await db.query(Lead).filter(
        Lead.email_verified == True,
        Lead.opted_out == False,
        Lead.last_contacted_at < (now() - timedelta(days=30))
    ).limit(remaining).all()
    
    # 4. For each lead: personalize, queue/approve, send
    for lead in leads:
        email = await personalizer.generate_with_fallback(lead)
        
        if config.APPROVAL_MODE:
            await queue.add_to_approval_queue(lead, email)
        else:
            result = await emailer.send(email)
            await audit.log_outreach(lead, 'email', result)
    
    # 5. Generate and send campaign report
    report = generate_campaign_report()
    await send_operator_report(report)
```

**Key Behaviors**:
- Enforce daily caps strictly (count sent today before starting)
- Exclude opted-out contacts at query level
- Enforce 30-day cooldown between contacts
- Distribute calls evenly across call window (e.g., 100 calls over 6 hours = 1 call every 3.6 minutes)
- Generate summary report and email to operators
- Handle scheduler failures gracefully (log, alert, don't crash)

### 7. Queue Manager

**Purpose**: Manage approval queue and outreach queue.

**Module**: `queue.py`

**Interface**:
```python
class QueueManager:
    async def add_to_approval_queue(self, lead: Lead, content: PersonalizedEmail) -> QueueItem:
        """Add item to approval queue."""
        pass
    
    async def get_approval_queue(self, limit: int = 50) -> List[QueueItem]:
        """Get pending approval items."""
        pass
    
    async def approve_item(self, item_id: int, operator_id: str) -> None:
        """Approve item and move to send queue."""
        pass
    
    async def reject_item(self, item_id: int, reason: str) -> None:
        """Reject item and remove from queue."""
        pass

@dataclass
class QueueItem:
    id: int
    lead_id: int
    outreach_type: str  # 'email' or 'call'
    content: dict
    status: str  # 'pending', 'approved', 'rejected', 'sent'
    created_at: datetime
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
```

**Storage**:
- Use database table `approval_queue` for persistence
- Optional: Redis for faster queue operations (enhancement)

**Key Behaviors**:
- Items expire after 7 days if not reviewed
- Operators can edit content before approving
- Approved items move to send queue automatically
- Track who approved what for audit purposes

### 8. Audit Logger

**Purpose**: Comprehensive logging of all system actions.

**Module**: `audit.py`

**Interface**:
```python
class AuditLogger:
    async def log_outreach(self, lead: Lead, outreach_type: str, result: dict) -> None:
        """Log outreach attempt."""
        pass
    
    async def log_opt_out(self, contact: str, method: str) -> None:
        """Log opt-out request."""
        pass
    
    async def log_api_call(self, service: str, endpoint: str, result: dict) -> None:
        """Log external API call."""
        pass
    
    async def log_error(self, component: str, error: Exception, context: dict) -> None:
        """Log error with context."""
        pass
```

**Log Storage**:
- Database table `audit_logs` for structured logs
- Stdout JSON logs for container environments
- Optional: Send to Sentry for error tracking

**Log Retention**:
- Outreach logs: 90 days (configurable)
- Opt-out logs: Indefinite (compliance requirement)
- Error logs: 30 days
- API call logs: 7 days

**Key Behaviors**:
- Mask sensitive data (API keys, full phone numbers) in logs
- Include correlation IDs for tracing requests
- Log at appropriate levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Structured logging with JSON format for parsing

## Data Models

### Database Schema (PostgreSQL)

```sql
-- Leads table
CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    business_name VARCHAR(255) NOT NULL,
    city VARCHAR(100),
    category VARCHAR(100),
    website VARCHAR(500),
    primary_email VARCHAR(255),
    primary_phone VARCHAR(20),
    raw_metadata JSONB,
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,
    verification_confidence FLOAT,
    opted_out BOOLEAN DEFAULT FALSE,
    opted_out_at TIMESTAMP,
    opted_out_method VARCHAR(50),
    last_contacted_at TIMESTAMP,
    contact_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(business_name, website, primary_phone)
);

CREATE INDEX idx_leads_verified ON leads(email_verified, phone_verified, opted_out);
CREATE INDEX idx_leads_last_contacted ON leads(last_contacted_at);

-- Verification results table
CREATE TABLE verification_results (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    verification_type VARCHAR(20) NOT NULL, -- 'email' or 'phone'
    contact_value VARCHAR(255) NOT NULL,
    is_valid BOOLEAN NOT NULL,
    confidence_score FLOAT,
    provider_name VARCHAR(50),
    provider_response JSONB,
    verified_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_verification_lead ON verification_results(lead_id);

-- Outreach history table
CREATE TABLE outreach_history (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    campaign_id INTEGER,
    outreach_type VARCHAR(20) NOT NULL, -- 'email' or 'call'
    content_hash VARCHAR(64),
    status VARCHAR(50) NOT NULL, -- 'sent', 'delivered', 'bounced', 'failed'
    provider_message_id VARCHAR(255),
    provider_response JSONB,
    outcome VARCHAR(50), -- for calls: 'answered', 'voicemail', 'busy', 'no-answer'
    duration_seconds INTEGER, -- for calls
    transcript TEXT, -- for calls
    recording_url VARCHAR(500), -- for calls
    attempted_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_outreach_lead ON outreach_history(lead_id);
CREATE INDEX idx_outreach_campaign ON outreach_history(campaign_id);
CREATE INDEX idx_outreach_attempted ON outreach_history(attempted_at);

-- Opt-outs table (never delete records)
CREATE TABLE opt_outs (
    id SERIAL PRIMARY KEY,
    contact_type VARCHAR(20) NOT NULL, -- 'email' or 'phone'
    contact_value VARCHAR(255) NOT NULL UNIQUE,
    opt_out_method VARCHAR(50), -- 'link', 'email_reply', 'call_request', 'sms'
    opted_out_at TIMESTAMP DEFAULT NOW(),
    source_lead_id INTEGER REFERENCES leads(id)
);

CREATE INDEX idx_optouts_contact ON opt_outs(contact_type, contact_value);

-- Approval queue table
CREATE TABLE approval_queue (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    outreach_type VARCHAR(20) NOT NULL,
    content JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'sent'
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '7 days'
);

CREATE INDEX idx_approval_status ON approval_queue(status, created_at);

-- Campaigns table
CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    campaign_type VARCHAR(20) NOT NULL, -- 'email' or 'call'
    total_attempted INTEGER DEFAULT 0,
    total_success INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    errors JSONB,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Audit logs table
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    log_level VARCHAR(20) NOT NULL,
    component VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    lead_id INTEGER,
    user_id VARCHAR(100),
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_created ON audit_logs(created_at);
CREATE INDEX idx_audit_component ON audit_logs(component, action);
```

### Pydantic Models

```python
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime

class LeadBase(BaseModel):
    source: str
    business_name: str
    city: Optional[str]
    category: Optional[str]
    website: Optional[str]
    primary_email: Optional[EmailStr]
    primary_phone: Optional[str]

class LeadCreate(LeadBase):
    raw_metadata: dict = {}

class Lead(LeadBase):
    id: int
    email_verified: bool = False
    phone_verified: bool = False
    verification_confidence: Optional[float]
    opted_out: bool = False
    last_contacted_at: Optional[datetime]
    contact_count: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class VerificationResult(BaseModel):
    lead_id: int
    verification_type: str
    contact_value: str
    is_valid: bool
    confidence_score: float
    provider_name: str
    provider_response: dict
    verified_at: datetime

class OutreachAttempt(BaseModel):
    lead_id: int
    campaign_id: Optional[int]
    outreach_type: str
    status: str
    provider_message_id: Optional[str]
    provider_response: dict
    attempted_at: datetime

class OptOut(BaseModel):
    contact_type: str
    contact_value: str
    opt_out_method: str
    opted_out_at: datetime
    source_lead_id: Optional[int]
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Source Restriction Properties

**Property 1: Approved sources only**
*For any* lead scraped by the system, the lead's source field must be in the configured list of approved public business sources.
**Validates: Requirements 1.1, 1.2**

**Property 2: Personal source rejection**
*For any* scrape attempt from a personal social media profile or non-public directory, the system must reject the source and return zero leads.
**Validates: Requirements 1.3**

**Property 3: Deduplication consistency**
*For any* set of leads with the same (business_name, website, primary_phone) combination, the system must maintain exactly one lead record.
**Validates: Requirements 1.4**

**Property 4: Rate limit backoff**
*For any* scraper that receives a rate limit response (HTTP 429), the system must implement exponential backoff with increasing delays between retries.
**Validates: Requirements 1.5, 8.4**

### Verification Properties

**Property 5: Email verification requirement**
*For any* lead processed for verification, if the lead has an email address, the system must call a verification provider and store the deliverability result.
**Validates: Requirements 2.1**

**Property 6: Personal email exclusion**
*For any* lead with an email address classified as personal (gmail, yahoo, hotmail) or undeliverable, the system must mark email_verified as False.
**Validates: Requirements 2.2**

**Property 7: Phone verification requirement**
*For any* lead with a phone number, the system must validate the number through a verification provider and store the validity result.
**Validates: Requirements 2.3**

**Property 8: Low confidence filtering**
*For any* verification result with a confidence score below the configured threshold, the system must flag the lead for exclusion or manual review.
**Validates: Requirements 2.4**

**Property 9: Verification persistence**
*For any* completed verification, storing the result and then retrieving it from the database must return all verification details (confidence score, provider response, timestamp).
**Validates: Requirements 2.5**

### Opt-out Properties

**Property 10: Unsubscribe link presence**
*For any* generated outreach email, the email body must contain an unsubscribe link with a unique token.
**Validates: Requirements 3.1**

**Property 11: Opt-out immediacy**
*For any* contact that triggers an unsubscribe action (link click, email reply, call request), the system must immediately set opted_out to True in the database.
**Validates: Requirements 3.2, 3.5**

**Property 12: Opt-out enforcement**
*For any* lead with opted_out set to True, attempting to send an email or place a call must be blocked and the lead must be skipped.
**Validates: Requirements 3.3**

**Property 13: Keyword detection**
*For any* email reply containing opt-out keywords (unsubscribe, stop, remove, opt-out), the system must detect the keyword and mark the sender as opted-out.
**Validates: Requirements 3.4**

### Rate Limiting Properties

**Property 14: Daily email cap enforcement**
*For any* daily email campaign, the total number of emails sent must not exceed the configured DAILY_EMAIL_CAP.
**Validates: Requirements 4.1**

**Property 15: Daily call cap enforcement**
*For any* daily call campaign, the total number of calls placed must not exceed the configured DAILY_CALL_CAP.
**Validates: Requirements 4.2**

**Property 16: Per-domain throttling**
*For any* domain, the number of emails sent to that domain within a 1-hour window must not exceed 5.
**Validates: Requirements 4.3**

**Property 17: Cooldown enforcement**
*For any* lead that has been contacted, attempting to contact the same lead again before the cooldown period (default 30 days) expires must be blocked.
**Validates: Requirements 4.5**

### Approval Mode Properties

**Property 18: Approval queue routing**
*For any* outreach content generated when approval mode is enabled, the content must be added to the approval queue and not sent immediately.
**Validates: Requirements 5.1**

**Property 19: Approval queue completeness**
*For any* item in the approval queue, the item must contain lead details, generated content, and personalization information.
**Validates: Requirements 5.2**

**Property 20: Approval workflow**
*For any* queued item that is approved by an operator, the system must move the item to the send queue and proceed with outreach.
**Validates: Requirements 5.3**

**Property 21: Approval bypass**
*For any* outreach content generated when approval mode is disabled, the content must be sent immediately without entering the approval queue.
**Validates: Requirements 5.5**

### Compliance Properties

**Property 22: Email compliance elements**
*For any* generated outreach email, the email must include sender's physical address, business identity (DevSync Innovation), and an unsubscribe link.
**Validates: Requirements 6.1**

**Property 23: Data minimization**
*For any* stored lead record, the record must contain only the specified fields (business_name, contact details, verification status, outreach history) and no additional sensitive personal information.
**Validates: Requirements 6.2**

**Property 24: Opt-out permanence**
*For any* opt-out record created, the record must never be deleted regardless of data retention policies.
**Validates: Requirements 6.3**

**Property 25: DNC list checking**
*For any* phone number that appears on the configured Do Not Call registry, the system must skip the contact and not place a call.
**Validates: Requirements 6.4**

### Scraper Properties

**Property 26: Data normalization**
*For any* scraper output, the returned leads must conform to the standardized lead object schema with fields for source, business_name, city, category, website, phone_numbers, emails, and raw_metadata.
**Validates: Requirements 8.5**

**Property 27: Retry exhaustion handling**
*For any* scraper that exhausts retry attempts (max 3), the system must log the failure and continue processing other sources without crashing.
**Validates: Requirements 8.4, 16.2**

### Personalization Properties

**Property 28: AI provider invocation**
*For any* verified lead selected for email outreach, the system must call the configured AI provider with lead context to generate personalized content.
**Validates: Requirements 9.1**

**Property 29: Content validation**
*For any* AI-generated email, the content must include a personalized hook, value proposition mentioning DevSync Innovation, and a call-to-action.
**Validates: Requirements 9.2**

**Property 30: Fallback on AI failure**
*For any* AI content generation that fails or times out, the system must fall back to a pre-configured template with variable substitution.
**Validates: Requirements 9.3**

**Property 31: Compliance footer appending**
*For any* finalized email content, the system must append compliance elements (address, identity, unsubscribe link) to the email body.
**Validates: Requirements 9.4**

**Property 32: Pre-send persistence**
*For any* email ready to send, the system must persist the complete email content to the database before transmission.
**Validates: Requirements 9.5**

### Email Sending Properties

**Property 33: Provider usage**
*For any* email sent, the system must use the configured email provider (SendGrid, Mailgun, or SMTP) with proper authentication.
**Validates: Requirements 10.1**

**Property 34: Transient error retry**
*For any* email send that fails with a transient error (rate limit, timeout), the system must retry using exponential backoff with a maximum of 3 attempts.
**Validates: Requirements 10.2**

**Property 35: Permanent error handling**
*For any* email send that fails with a permanent error (invalid recipient, blocked), the system must mark the lead as undeliverable and exclude it from future campaigns.
**Validates: Requirements 10.3**

**Property 36: Webhook processing**
*For any* webhook notification received from the email provider, the system must process the event and update the corresponding lead status in the database.
**Validates: Requirements 10.4**

### Voice Call Properties

**Property 37: Call initiation**
*For any* voice call initiated, the system must use the configured telephony provider (Twilio or Exotel) to place the call to the verified phone number.
**Validates: Requirements 11.1**

**Property 38: TTS introduction**
*For any* call that is answered, the system must play a TTS message identifying the caller as DevSync Innovation and stating the call purpose.
**Validates: Requirements 11.2**

**Property 39: Voicemail handling**
*For any* call where voicemail is detected, the system must leave a pre-recorded message and mark the lead with a cooldown period (default 7 days).
**Validates: Requirements 11.4**

**Property 40: Call logging**
*For any* completed call, the system must store the call outcome, duration, transcript (if available), and recording reference to the database.
**Validates: Requirements 11.5**

### Scheduler Properties

**Property 41: Campaign lead selection**
*For any* scheduled campaign execution, the system must select only verified leads where opted_out is False and last_contacted_at is older than the cooldown period.
**Validates: Requirements 12.1, 12.3**

**Property 42: Campaign report generation**
*For any* completed daily campaign, the system must generate a summary report including total attempted, total success, total failed, and errors encountered.
**Validates: Requirements 12.4**

**Property 43: Critical error handling**
*For any* critical error encountered during campaign execution (database unavailable, all providers failing), the system must halt the campaign, log the error, and alert operators.
**Validates: Requirements 12.5**

### Dry-run Mode Properties

**Property 44: Dry-run simulation**
*For any* campaign executed when dry-run mode is enabled, the system must execute all logic (lead selection, content generation) but must not send actual emails or place actual calls.
**Validates: Requirements 14.1**

**Property 45: Dry-run logging**
*For any* action simulated in dry-run mode, the system must log what would have been done (email would be sent to X, call would be placed to Y).
**Validates: Requirements 14.2**

**Property 46: Dry-run cap enforcement**
*For any* campaign in dry-run mode, the system must still enforce daily caps and rate limits to accurately simulate production behavior.
**Validates: Requirements 14.3**

**Property 47: Live mode execution**
*For any* campaign executed when dry-run mode is disabled, the system must send actual emails and place actual calls.
**Validates: Requirements 14.5**

### Data Persistence Properties

**Property 48: Lead storage round-trip**
*For any* lead stored in the database, retrieving the lead by ID must return all persisted fields with their original values.
**Validates: Requirements 15.2**

**Property 49: Outreach history round-trip**
*For any* outreach attempt recorded, retrieving the record must return all attempt details including timestamp, status, provider response, and outcome.
**Validates: Requirements 15.3**

**Property 50: Opt-out permanence**
*For any* opt-out record created, the record must remain in the database indefinitely and never be deleted by retention policies.
**Validates: Requirements 15.4**

### Error Handling Properties

**Property 51: Exponential backoff on transient failures**
*For any* third-party API call that fails with a transient error, the system must retry with exponentially increasing delays (1s, 2s, 4s, etc.) up to 3 attempts.
**Validates: Requirements 16.1**

**Property 52: Failure isolation**
*For any* individual lead or outreach attempt that fails after exhausting retries, the system must mark that item as failed and continue processing other items without stopping.
**Validates: Requirements 16.2**

**Property 53: Circuit breaker activation**
*For any* API provider that fails consistently (e.g., 5 consecutive failures), the system must temporarily disable that provider and alert operators.
**Validates: Requirements 16.3**

### Configuration Properties

**Property 54: Required config validation**
*For any* required environment variable that is missing at startup, the system must fail to start and display an error message indicating which variable is required.
**Validates: Requirements 17.2**

**Property 55: Invalid config rejection**
*For any* configuration value that is invalid (negative daily cap, invalid timezone), the system must validate at startup and fail with a descriptive error message.
**Validates: Requirements 17.3**

**Property 56: Sensitive data masking**
*For any* log entry that would contain sensitive configuration values (API keys, passwords), the system must mask or redact the values before logging.
**Validates: Requirements 17.4**

**Property 57: Default value usage**
*For any* optional configuration not provided, the system must use the documented default value (e.g., daily caps of 100, approval mode enabled, 30-day cooldown).
**Validates: Requirements 17.5**



## Error Handling

### Error Categories

1. **Transient Errors**: Temporary failures that may succeed on retry
   - Network timeouts
   - Rate limit responses (HTTP 429)
   - Server errors (HTTP 5xx)
   - Database connection timeouts

2. **Permanent Errors**: Failures that will not succeed on retry
   - Invalid API credentials (HTTP 401)
   - Resource not found (HTTP 404)
   - Invalid email format
   - Blocked domain

3. **Critical Errors**: System-level failures requiring immediate attention
   - Database unavailable
   - All API providers failing
   - Configuration errors
   - Disk space exhausted

### Retry Strategy

**Exponential Backoff with Jitter**:
```python
def calculate_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate exponential backoff with jitter."""
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
    return delay + jitter

# Usage
for attempt in range(3):
    try:
        result = await api_call()
        break
    except TransientError as e:
        if attempt < 2:
            await asyncio.sleep(calculate_backoff(attempt))
        else:
            logger.error(f"Exhausted retries: {e}")
            raise
```

### Circuit Breaker Pattern

**Implementation**:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                await alert_operators(f"Circuit breaker opened for {func.__name__}")
            raise
```

### Error Logging

**Structured Error Logs**:
```python
logger.error(
    "Email send failed",
    extra={
        "lead_id": lead.id,
        "email": lead.primary_email,
        "provider": "sendgrid",
        "error_type": "permanent",
        "error_code": "invalid_recipient",
        "correlation_id": correlation_id
    }
)
```

### Alerting

**Alert Triggers**:
- Circuit breaker opens for any provider
- Daily cap reached
- Database connection lost for > 5 minutes
- More than 50% of outreach attempts failing
- Opt-out rate exceeds 5% in a single campaign

**Alert Channels**:
- Email to configured operator addresses
- Optional: Slack webhook
- Optional: PagerDuty for critical alerts

## Testing Strategy

### Unit Testing

**Framework**: pytest with pytest-asyncio for async tests

**Coverage Areas**:
- Data validation (Pydantic models)
- Business logic (verification, personalization, rate limiting)
- Database operations (CRUD, queries)
- Utility functions (phone normalization, email parsing)

**Example Unit Tests**:
```python
def test_phone_normalization():
    """Test phone number normalization to E.164 format."""
    assert normalize_phone("+91 98765 43210") == "+919876543210"
    assert normalize_phone("9876543210", country="IN") == "+919876543210"

def test_email_domain_extraction():
    """Test email domain extraction for throttling."""
    assert extract_domain("contact@example.com") == "example.com"
    assert extract_domain("info@subdomain.example.com") == "example.com"

@pytest.mark.asyncio
async def test_daily_cap_enforcement():
    """Test that daily email cap is enforced."""
    config.DAILY_EMAIL_CAP = 10
    # Send 10 emails
    for i in range(10):
        result = await send_email(create_test_email())
        assert result.success
    
    # 11th email should be blocked
    result = await send_email(create_test_email())
    assert not result.success
    assert "daily cap reached" in result.error.lower()
```

### Property-Based Testing

**Framework**: Hypothesis (Python property-based testing library)

**Configuration**: Each property test should run a minimum of 100 iterations to ensure thorough coverage of the input space.

**Test Tagging**: Each property-based test must include a comment explicitly referencing the correctness property from the design document using the format: `# Feature: devsync-sales-ai, Property {number}: {property_text}`

**Example Property Tests**:

```python
from hypothesis import given, strategies as st

@given(st.lists(st.builds(Lead), min_size=1, max_size=100))
def test_property_3_deduplication(leads):
    """
    Feature: devsync-sales-ai, Property 3: Deduplication consistency
    For any set of leads with the same (business_name, website, primary_phone),
    the system must maintain exactly one lead record.
    """
    # Create duplicates
    duplicate_lead = leads[0]
    leads_with_dupes = leads + [duplicate_lead, duplicate_lead]
    
    # Process through deduplication
    deduplicated = deduplicate_leads(leads_with_dupes)
    
    # Check uniqueness
    unique_keys = set()
    for lead in deduplicated:
        key = (lead.business_name, lead.website, lead.primary_phone)
        assert key not in unique_keys, "Duplicate lead found"
        unique_keys.add(key)

@given(st.integers(min_value=1, max_value=1000))
def test_property_14_daily_email_cap(cap):
    """
    Feature: devsync-sales-ai, Property 14: Daily email cap enforcement
    For any daily email campaign, the total number of emails sent must not
    exceed the configured DAILY_EMAIL_CAP.
    """
    config.DAILY_EMAIL_CAP = cap
    reset_daily_counters()
    
    # Attempt to send cap + 10 emails
    sent_count = 0
    for i in range(cap + 10):
        result = send_email_sync(create_test_email())
        if result.success:
            sent_count += 1
    
    assert sent_count == cap, f"Sent {sent_count} emails, expected {cap}"

@given(st.emails())
def test_property_10_unsubscribe_link(email_address):
    """
    Feature: devsync-sales-ai, Property 10: Unsubscribe link presence
    For any generated outreach email, the email body must contain an
    unsubscribe link with a unique token.
    """
    lead = create_test_lead(email=email_address)
    generated_email = generate_email(lead)
    
    # Check for unsubscribe link
    assert "unsubscribe" in generated_email.body_html.lower()
    assert "unsubscribe" in generated_email.body_text.lower()
    
    # Extract and verify token is unique
    token = extract_unsubscribe_token(generated_email.body_html)
    assert token is not None
    assert len(token) >= 32  # UUID4 length

@given(st.booleans())
def test_property_44_dry_run_simulation(dry_run_enabled):
    """
    Feature: devsync-sales-ai, Property 44: Dry-run simulation
    For any campaign executed when dry-run mode is enabled, the system must
    execute all logic but must not send actual emails or place actual calls.
    """
    config.DRY_RUN_MODE = dry_run_enabled
    
    with patch('outreach.emailer.send_via_provider') as mock_send:
        campaign = execute_email_campaign_sync()
        
        if dry_run_enabled:
            # In dry-run, provider should not be called
            mock_send.assert_not_called()
            assert campaign.total_attempted > 0  # Logic executed
        else:
            # In live mode, provider should be called
            assert mock_send.call_count > 0
```

### Integration Testing

**Scope**: Test interactions between components with real database and mocked external APIs.

**Test Scenarios**:
- End-to-end campaign execution (scrape → verify → personalize → send)
- Webhook processing (receive bounce → update lead status)
- Approval workflow (generate → queue → approve → send)
- Opt-out flow (unsubscribe link click → update database → verify exclusion)

**Example Integration Test**:
```python
@pytest.mark.integration
async def test_end_to_end_email_campaign(test_db):
    """Test complete email campaign flow."""
    # 1. Create verified leads
    leads = [create_verified_lead() for _ in range(5)]
    for lead in leads:
        await db.save(lead)
    
    # 2. Execute campaign
    config.APPROVAL_MODE = False
    config.DRY_RUN_MODE = False
    campaign = await execute_email_campaign()
    
    # 3. Verify results
    assert campaign.total_attempted == 5
    assert campaign.total_success == 5
    
    # 4. Verify database updates
    for lead in leads:
        updated_lead = await db.get_lead(lead.id)
        assert updated_lead.last_contacted_at is not None
        assert updated_lead.contact_count == 1
    
    # 5. Verify outreach history
    history = await db.get_outreach_history(campaign.id)
    assert len(history) == 5
```

### Test Data Generation

**Strategies for Generators**:
- **Leads**: Generate with valid business names, domains, phone numbers in E.164 format
- **Emails**: Use hypothesis `st.emails()` for valid email addresses
- **Phone Numbers**: Generate valid E.164 numbers for specific countries
- **Verification Results**: Generate with confidence scores between 0.0 and 1.0
- **Timestamps**: Use hypothesis `st.datetimes()` with reasonable bounds

**Smart Generators**:
```python
@st.composite
def business_lead(draw):
    """Generate realistic business lead."""
    return Lead(
        source=draw(st.sampled_from(["google_maps", "justdial", "indiamart"])),
        business_name=draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', ' ')))),
        city=draw(st.sampled_from(["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata"])),
        category=draw(st.sampled_from(["restaurant", "retail", "services", "manufacturing"])),
        website=draw(st.from_regex(r"https?://[a-z0-9-]+\.[a-z]{2,}", fullmatch=True)),
        primary_email=draw(st.emails()),
        primary_phone=draw(st.from_regex(r"\+91[6-9]\d{9}", fullmatch=True)),
        email_verified=draw(st.booleans()),
        phone_verified=draw(st.booleans())
    )
```

### Manual Testing Checklist

Before production deployment:
- [ ] Verify SPF, DKIM, DMARC records for sending domain
- [ ] Test unsubscribe link functionality end-to-end
- [ ] Verify webhook endpoints are accessible from provider IPs
- [ ] Test dry-run mode with real configuration
- [ ] Verify approval queue workflow in dashboard
- [ ] Test opt-out enforcement (add contact to opt-out list, verify exclusion)
- [ ] Verify daily caps are enforced
- [ ] Test error alerting (simulate provider failure)
- [ ] Verify call flow with test phone number
- [ ] Review generated email content for quality and compliance

## Deployment Architecture

### Container Structure

**Docker Compose Services**:
```yaml
services:
  backend:
    build: ./backend
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - db
      - redis
    ports:
      - "8000:8000"
  
  scheduler:
    build: ./backend
    command: python -m app.scheduler
    environment:
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - db
  
  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=devsync_sales
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### Render.com Deployment

**render.yaml**:
```yaml
services:
  - type: web
    name: devsync-sales-api
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: devsync-sales-db
          property: connectionString
      - key: PYTHON_VERSION
        value: 3.10.0
  
  - type: worker
    name: devsync-sales-scheduler
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python -m app.scheduler"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: devsync-sales-db
          property: connectionString
  
  - type: cron
    name: daily-email-campaign
    schedule: "0 4 * * *"  # 10:00 IST = 04:30 UTC
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python -m app.scripts.run_campaign --type email"

databases:
  - name: devsync-sales-db
    databaseName: devsync_sales
    user: devsync_user
```

### Environment Configuration

**Production Environment Variables**:
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/devsync_sales

# Email Provider (choose one)
SENDGRID_API_KEY=SG.xxx
# OR
MAILGUN_API_KEY=key-xxx
MAILGUN_DOMAIN=mg.devsyncinnovation.com
# OR
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=marketing@devsyncinnovation.com
SMTP_PASSWORD=xxx

# Email Configuration
EMAIL_FROM=marketing@devsyncinnovation.com
EMAIL_FROM_NAME=DevSync Innovation
BUSINESS_ADDRESS="123 Tech Park, Bangalore, Karnataka 560001, India"

# Verification Providers
ABSTRACTAPI_KEY=xxx
NUMVERIFY_KEY=xxx

# Telephony
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=+919876543210

# AI Services
OPENAI_API_KEY=sk-xxx
ELEVENLABS_API_KEY=xxx

# Operational Settings
DAILY_EMAIL_CAP=100
DAILY_CALL_CAP=100
COOLDOWN_DAYS=30
APPROVAL_MODE=true
DRY_RUN_MODE=false
TIMEZONE=Asia/Kolkata

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
LOG_LEVEL=INFO
```

### Monitoring and Observability

**Metrics to Track**:
- Emails sent per day
- Calls placed per day
- Verification success rate
- Email delivery rate
- Bounce rate
- Opt-out rate
- API error rate per provider
- Campaign execution time

**Logging Strategy**:
- Structured JSON logs to stdout
- Log aggregation via Render logs or external service (Datadog, Logtail)
- Separate log levels for different environments (DEBUG in dev, INFO in prod)

**Health Checks**:
```python
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    checks = {
        "database": await check_database_connection(),
        "redis": await check_redis_connection(),
        "email_provider": await check_email_provider(),
        "verification_provider": await check_verification_provider()
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={"status": "healthy" if all_healthy else "unhealthy", "checks": checks}
    )
```

## Security Considerations

### API Key Management

- Store all API keys in environment variables, never in code
- Use secret management service (Render secrets, AWS Secrets Manager) in production
- Rotate API keys quarterly
- Mask API keys in logs (show only first 4 and last 4 characters)

### Data Protection

- Encrypt database connections (SSL/TLS)
- Hash unsubscribe tokens before storing
- Implement rate limiting on API endpoints (100 requests/minute per IP)
- Validate all user inputs (Pydantic models)
- Sanitize HTML in generated emails to prevent XSS

### Access Control

- Dashboard requires authentication (implement JWT or session-based auth)
- Role-based access: operators can approve/reject, admins can change configuration
- Audit log all operator actions (who approved what, when)

### Compliance

- Provide data export API for GDPR subject access requests
- Implement data deletion API (right to be forgotten)
- Maintain opt-out list indefinitely
- Include privacy policy link in all emails
- Log consent for call recordings

## Future Enhancements

### Phase 2 Features

1. **A/B Testing**: Test different email templates and measure response rates
2. **Lead Scoring**: ML model to predict lead quality and prioritize outreach
3. **Multi-channel Sequences**: Automated follow-up sequences (email → call → email)
4. **CRM Integration**: Sync leads and outcomes with Salesforce, HubSpot
5. **Advanced Analytics**: Dashboard with conversion funnels, ROI tracking
6. **SMS Outreach**: Add SMS as third outreach channel
7. **Webhook API**: Allow external systems to trigger campaigns
8. **Custom Templates**: Operator-defined email and call script templates
9. **Geo-targeting**: Target businesses in specific regions or cities
10. **Industry-specific Personalization**: Tailored messaging per business category

### Scalability Improvements

- Move to Redis-based queue for higher throughput
- Implement worker pool for parallel outreach
- Add read replicas for database queries
- Cache verification results in Redis
- Implement rate limiting with token bucket algorithm
- Add CDN for dashboard assets

## Conclusion

This design provides a comprehensive, production-ready architecture for DevSyncSalesAI that prioritizes compliance, safety, and operator control. The modular design allows for incremental development and testing, while the extensive correctness properties ensure the system behaves as specified across all scenarios.

The system defaults to safe settings (dry-run mode, approval required, low caps) and requires explicit operator action to transition to live outreach, minimizing the risk of accidental mass outreach or compliance violations.
