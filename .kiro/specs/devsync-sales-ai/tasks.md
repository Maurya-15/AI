# Implementation Plan

- [x] 1. Set up project structure and core configuration




  - Create backend directory structure with app/, tests/, scripts/ folders
  - Set up FastAPI application with main.py entry point
  - Create config.py with environment variable loading and validation using Pydantic Settings
  - Create .env.example with all required and optional environment variables
  - Set up requirements.txt with core dependencies (FastAPI, SQLAlchemy, httpx, APScheduler, Hypothesis, pytest)
  - Create Dockerfile for backend service
  - Create docker-compose.yml for local development (backend, postgres, redis)
  - _Requirements: 17.1, 17.2, 17.3, 17.5_





- [ ] 1.1 Write property test for configuration validation
  - **Property 54: Required config validation**

  - **Validates: Requirements 17.2**

- [x] 1.2 Write property test for invalid config rejection

  - **Property 55: Invalid config rejection**



  - **Validates: Requirements 17.3**

- [ ] 1.3 Write property test for default value usage
  - **Property 57: Default value usage**
  - **Validates: Requirements 17.5**

- [x] 2. Implement database models and connection


  - Create db.py with SQLAlchemy engine and session management
  - Define database models in models.py (Lead, VerificationResult, OutreachHistory, OptOut, ApprovalQueue, Campaign, AuditLog)

  - Create Pydantic schemas for API request/response validation
  - Implement database initialization and migration logic
  - Add database indexes for performance (verification status, last_contacted_at, opt_out status)

  - _Requirements: 15.1, 15.2, 15.3, 15.4_




- [ ] 2.1 Write property test for lead storage round-trip
  - **Property 48: Lead storage round-trip**
  - **Validates: Requirements 15.2**

- [ ] 2.2 Write property test for outreach history round-trip
  - **Property 49: Outreach history round-trip**







  - **Validates: Requirements 15.3**

- [ ] 2.3 Write property test for opt-out permanence
  - **Property 50: Opt-out permanence**
  - **Validates: Requirements 15.4**

- [x] 3. Implement audit logging system


  - Create audit.py with AuditLogger class
  - Implement structured logging with JSON format



  - Add methods for logging outreach attempts, opt-outs, API calls, and errors

  - Implement log masking for sensitive data (API keys, passwords)

  - Set up log retention policies

  - _Requirements: 7.1, 7.2, 7.3, 7.4, 17.4_



- [ ] 3.1 Write property test for sensitive data masking
  - **Property 56: Sensitive data masking**
  - **Validates: Requirements 17.4**







- [x] 4. Implement scraper base class and adapters


  - Create scraper/base.py with BaseScraper abstract class

  - Implement scraper/google_maps.py using Google Maps Places API
  - Implement scraper/justdial.py with HTML parsing and robots.txt respect
  - Implement scraper/linkedin_company.py for public company pages


  - Add phone number normalization to E.164 format


  - Implement deduplication logic based on (business_name, website, phone) composite key
  - Add exponential backoff with jitter for rate limit handling
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 8.1, 8.2, 8.3, 8.4, 8.5_



- [x] 4.1 Write property test for approved sources only

  - **Property 1: Approved sources only**

  - **Validates: Requirements 1.1, 1.2**



- [ ] 4.2 Write property test for personal source rejection




  - **Property 2: Personal source rejection**
  - **Validates: Requirements 1.3**



- [ ] 4.3 Write property test for deduplication consistency
  - **Property 3: Deduplication consistency**
  - **Validates: Requirements 1.4**



- [ ] 4.4 Write property test for rate limit backoff
  - **Property 4: Rate limit backoff**

  - **Validates: Requirements 1.5, 8.4**

- [x] 4.5 Write property test for data normalization

  - **Property 26: Data normalization**





  - **Validates: Requirements 8.5**



- [ ] 4.6 Write property test for retry exhaustion handling
  - **Property 27: Retry exhaustion handling**
  - **Validates: Requirements 8.4, 16.2**

- [ ] 5. Implement verification services
  - Create verifier/email_verify.py with EmailVerifier class
  - Integrate AbstractAPI/ZeroBounce/Hunter for email verification

  - Implement personal email provider detection (gmail, yahoo, hotmail, outlook)
  - Create verifier/phone_verify.py with PhoneVerifier class


  - Integrate Twilio Lookup or NumVerify for phone verification
  - Implement verification result caching (30-day TTL)
  - Add confidence score thresholding (0.7 for emails, 0.6 for phones)


  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_


- [x] 5.1 Write property test for email verification requirement


  - **Property 5: Email verification requirement**

  - **Validates: Requirements 2.1**



- [ ] 5.2 Write property test for personal email exclusion
  - **Property 6: Personal email exclusion**
  - **Validates: Requirements 2.2**




- [x] 5.3 Write property test for phone verification requirement

  - **Property 7: Phone verification requirement**

  - **Validates: Requirements 2.3**


- [x] 5.4 Write property test for low confidence filtering





  - **Property 8: Low confidence filtering**

  - **Validates: Requirements 2.4**


- [ ] 5.5 Write property test for verification persistence
  - **Property 9: Verification persistence**

  - **Validates: Requirements 2.5**



- [ ] 6. Implement personalization service
  - Create outreach/personalizer.py with EmailPersonalizer class

  - Integrate OpenAI GPT-4 or AIMLAPI for content generation

  - Implement AI prompt template with lead context (business name, category, city)

  - Create fallback template system with variable substitution
  - Add content validation (length, required elements)

  - Implement 5-second timeout for AI calls

  - _Requirements: 9.1, 9.2, 9.3_

- [ ] 6.1 Write property test for AI provider invocation
  - **Property 28: AI provider invocation**
  - **Validates: Requirements 9.1**

- [ ] 6.2 Write property test for content validation
  - **Property 29: Content validation**
  - **Validates: Requirements 9.2**

- [x] 6.3 Write property test for fallback on AI failure

  - **Property 30: Fallback on AI failure**
  - **Validates: Requirements 9.3**


- [x] 7. Implement email outreach service




  - Create outreach/emailer.py with EmailSender class
  - Implement SendGrid adapter with API integration

  - Implement Mailgun adapter as alternative
  - Implement SMTP adapter as fallback
  - Add unsubscribe link generation with unique UUID tokens

  - Implement compliance footer with business address and identity
  - Add per-domain throttling (max 5 emails/hour/domain)
  - Implement retry logic with exponential backoff (3 attempts)

  - Add webhook endpoint for bounce/complaint/unsubscribe events
  - _Requirements: 3.1, 6.1, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 7.1 Write property test for unsubscribe link presence

  - **Property 10: Unsubscribe link presence**
  - **Validates: Requirements 3.1**


- [ ] 7.2 Write property test for email compliance elements
  - **Property 22: Email compliance elements**
  - **Validates: Requirements 6.1**


- [ ] 7.3 Write property test for compliance footer appending
  - **Property 31: Compliance footer appending**

  - **Validates: Requirements 9.4**

- [x] 7.4 Write property test for pre-send persistence

  - **Property 32: Pre-send persistence**
  - **Validates: Requirements 9.5**


- [ ] 7.5 Write property test for provider usage
  - **Property 33: Provider usage**
  - **Validates: Requirements 10.1**


- [ ] 7.6 Write property test for transient error retry
  - **Property 34: Transient error retry**

  - **Validates: Requirements 10.2**

- [x] 7.7 Write property test for permanent error handling


  - **Property 35: Permanent error handling**



  - **Validates: Requirements 10.3**

- [ ] 7.8 Write property test for webhook processing
  - **Property 36: Webhook processing**
  - **Validates: Requirements 10.4**

- [x] 7.9 Write property test for per-domain throttling

  - **Property 16: Per-domain throttling**
  - **Validates: Requirements 4.3**


- [ ] 8. Implement opt-out handling
  - Add unsubscribe endpoint to handle link clicks
  - Implement keyword detection for email replies (unsubscribe, stop, remove, opt-out)

  - Create opt-out enforcement checks in campaign execution
  - Add opt-out status to lead queries
  - Implement opt-out permanence (never delete opt-out records)


  - _Requirements: 3.2, 3.3, 3.4, 3.5, 6.3_




- [ ] 8.1 Write property test for opt-out immediacy
  - **Property 11: Opt-out immediacy**
  - **Validates: Requirements 3.2, 3.5**

- [ ] 8.2 Write property test for opt-out enforcement
  - **Property 12: Opt-out enforcement**
  - **Validates: Requirements 3.3**

- [ ] 8.3 Write property test for keyword detection
  - **Property 13: Keyword detection**

  - **Validates: Requirements 3.4**

- [x] 8.4 Write property test for opt-out permanence (data retention)

  - **Property 24: Opt-out permanence**
  - **Validates: Requirements 6.3**


- [ ] 9. Implement voice call service
  - Create outreach/caller.py with VoiceCaller class
  - Integrate Twilio Programmable Voice API

  - Implement call flow with TTS introduction message
  - Add ASR for intent detection (interested, not interested, remove, call back)
  - Implement voicemail detection and message leaving

  - Add call outcome tracking (answered, voicemail, busy, no-answer)
  - Store call transcripts and recording references





  - Implement call window enforcement (11:00-17:00 IST, weekdays only)
  - Add Do Not Call registry checking
  - _Requirements: 6.4, 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ] 9.1 Write property test for call initiation
  - **Property 37: Call initiation**

  - **Validates: Requirements 11.1**



- [ ] 9.2 Write property test for TTS introduction
  - **Property 38: TTS introduction**
  - **Validates: Requirements 11.2**




- [x] 9.3 Write property test for voicemail handling

  - **Property 39: Voicemail handling**




  - **Validates: Requirements 11.4**

- [x] 9.4 Write property test for call logging

  - **Property 40: Call logging**
  - **Validates: Requirements 11.5**


- [ ] 9.5 Write property test for DNC list checking

  - **Property 25: DNC list checking**

  - **Validates: Requirements 6.4**



- [x] 10. Implement queue manager

  - Create queue.py with QueueManager class



  - Implement approval queue with database-backed storage
  - Add methods for adding items to queue, retrieving pending items
  - Implement approve/reject/edit functionality
  - Add queue item expiration (7 days)
  - Track reviewer identity and timestamp for audit
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 10.1 Write property test for approval queue routing
  - **Property 18: Approval queue routing**

  - **Validates: Requirements 5.1**



- [ ] 10.2 Write property test for approval queue completeness
  - **Property 19: Approval queue completeness**


  - **Validates: Requirements 5.2**

- [x] 10.3 Write property test for approval workflow

  - **Property 20: Approval workflow**
  - **Validates: Requirements 5.3**

- [ ] 10.4 Write property test for approval bypass
  - **Property 21: Approval bypass**
  - **Validates: Requirements 5.5**

- [ ] 11. Implement rate limiting and caps
  - Add daily email cap enforcement in campaign execution
  - Add daily call cap enforcement in campaign execution
  - Implement per-domain email throttling (5 emails/hour/domain)
  - Add per-country call cap enforcement
  - Implement cooldown period enforcement (30 days between contacts)
  - Create rate limit tracking in database or Redis
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 11.1 Write property test for daily email cap enforcement
  - **Property 14: Daily email cap enforcement**
  - **Validates: Requirements 4.1**

- [ ] 11.2 Write property test for daily call cap enforcement
  - **Property 15: Daily call cap enforcement**
  - **Validates: Requirements 4.2**

- [ ] 11.3 Write property test for cooldown enforcement
  - **Property 17: Cooldown enforcement**
  - **Validates: Requirements 4.5**

- [ ] 12. Implement scheduler service
  - Create scheduler.py with CampaignScheduler class using APScheduler
  - Implement daily email campaign job (default 10:00 IST)
  - Implement daily call campaign job (default 11:00-17:00 IST)
  - Add campaign execution logic with lead selection (verified, non-opted-out, cooldown respected)
  - Implement call distribution across call window
  - Add campaign report generation with statistics
  - Implement operator email notification with campaign summary
  - Add critical error handling (halt campaign, log, alert)
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 12.1 Write property test for campaign lead selection
  - **Property 41: Campaign lead selection**
  - **Validates: Requirements 12.1, 12.3**

- [ ] 12.2 Write property test for campaign report generation
  - **Property 42: Campaign report generation**
  - **Validates: Requirements 12.4**

- [ ] 12.3 Write property test for critical error handling
  - **Property 43: Critical error handling**
  - **Validates: Requirements 12.5**

- [ ] 13. Implement dry-run mode
  - Add DRY_RUN_MODE configuration flag
  - Implement dry-run logic in email sender (log instead of send)
  - Implement dry-run logic in voice caller (log instead of call)
  - Add dry-run logging for all simulated actions
  - Ensure caps and rate limits are enforced in dry-run mode
  - Add confirmation prompt when disabling dry-run mode
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

- [ ] 13.1 Write property test for dry-run simulation
  - **Property 44: Dry-run simulation**
  - **Validates: Requirements 14.1**

- [ ] 13.2 Write property test for dry-run logging
  - **Property 45: Dry-run logging**
  - **Validates: Requirements 14.2**

- [ ] 13.3 Write property test for dry-run cap enforcement
  - **Property 46: Dry-run cap enforcement**
  - **Validates: Requirements 14.3**

- [x] 13.4 Write property test for live mode execution

  - **Property 47: Live mode execution**
  - **Validates: Requirements 14.5**

- [x] 14. Implement error handling and resilience

  - Create error handling utilities with retry logic and exponential backoff
  - Implement circuit breaker pattern for API providers
  - Add failure isolation (continue processing on individual failures)
  - Implement network connectivity detection and pause/resume
  - Add database reconnection logic with exponential backoff
  - Create alerting system for critical errors
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [x] 14.1 Write property test for exponential backoff on transient failures

  - **Property 51: Exponential backoff on transient failures**
  - **Validates: Requirements 16.1**

- [x] 14.2 Write property test for failure isolation

  - **Property 52: Failure isolation**
  - **Validates: Requirements 16.2**

- [x] 14.3 Write property test for circuit breaker activation

  - **Property 53: Circuit breaker activation**
  - **Validates: Requirements 16.3**

- [x] 15. Implement FastAPI endpoints

  - Create health check endpoint (/health)
  - Create lead management endpoints (GET /leads, POST /leads, GET /leads/{id})
  - Create approval queue endpoints (GET /approval-queue, POST /approval-queue/{id}/approve, POST /approval-queue/{id}/reject)
  - Create outreach history endpoints (GET /outreach-history)
  - Create opt-out endpoints (POST /unsubscribe, GET /opt-outs)
  - Create campaign endpoints (GET /campaigns, POST /campaigns/trigger)
  - Add webhook endpoints for email provider callbacks
  - Implement request validation with Pydantic models
  - Add CORS middleware for dashboard access
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [x] 16. Create React dashboard

  - Set up React project with Vite and TailwindCSS
  - Create dashboard overview page with campaign statistics
  - Create approval queue page with approve/reject/edit functionality
  - Create outreach history page with pagination and filtering
  - Create lead search page with search functionality
  - Create opt-out management page
  - Implement API client for backend communication
  - Add authentication (JWT or session-based)
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [x] 17. Create deployment configuration

  - Create render.yaml for Render.com deployment
  - Configure web service for FastAPI backend
  - Configure worker service for scheduler
  - Configure cron jobs for daily campaigns
  - Set up PostgreSQL database on Render
  - Document environment variable configuration
  - Create deployment guide in README
  - _Requirements: 17.1_

- [x] 18. Implement compliance and safety features

  - Add data minimization checks (only store required fields)
  - Implement data retention policies with automatic purging
  - Create data export API for GDPR subject access requests
  - Add safe defaults (dry-run enabled, approval enabled, low caps)
  - Implement warning prompts for disabling safety features
  - Add SPF/DKIM/DMARC validation checks for production
  - Create compliance checklist in README
  - _Requirements: 6.2, 6.3, 6.5, 18.1, 18.2, 18.3, 18.4, 18.5_

- [x] 18.1 Write property test for data minimization

  - **Property 23: Data minimization**
  - **Validates: Requirements 6.2**

- [x] 19. Create seed data and test scripts

  - Create scripts/seed_leads.py to populate test leads
  - Create scripts/run_once.py for manual campaign execution
  - Create scripts/test_email.py to send test email
  - Create scripts/test_call.py to place test call
  - Add sample data fixtures for testing
  - _Requirements: 1.1_

- [x] 20. Write comprehensive documentation

  - Create main README.md with project overview and setup instructions
  - Document API key acquisition (Twilio, SendGrid, AbstractAPI, OpenAI)
  - Document SPF/DKIM/DMARC configuration for email domain
  - Create compliance checklist (CAN-SPAM, TRAI, GDPR)
  - Document dry-run vs live mode operation
  - Document approval mode configuration
  - Document daily cap adjustment
  - Add troubleshooting guide
  - Create dashboard README with usage instructions
  - Add legal disclaimer and operator responsibility notice
  - _Requirements: 6.1, 17.1, 18.1_

- [x] 21. Final checkpoint - Ensure all tests pass


  - Ensure all tests pass, ask the user if questions arise.



