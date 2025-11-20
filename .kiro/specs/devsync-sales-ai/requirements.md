# Requirements Document

## Introduction

DevSyncSalesAI is an AI-driven, compliant business outreach system designed for DevSync Innovation to automate the discovery, verification, and outreach to publicly-listed business leads through email and voice calls. The system prioritizes safety, legal compliance, observability, and operator control while strictly limiting contact to verified business entities with publicly available contact information.

## Glossary

- **System**: The DevSyncSalesAI platform including all backend services, database, scheduler, and dashboard components
- **Lead**: A business entity with publicly-listed contact information (email and/or phone) that has been scraped from approved public sources
- **Verified Lead**: A lead that has passed both email and phone verification checks with acceptable confidence scores
- **Operator**: A human user of DevSync Innovation who reviews, approves, and monitors outreach campaigns
- **Outreach**: The act of contacting a verified lead via email or voice call
- **Opt-out**: A request from a contact to cease all future communications, which must be honored immediately
- **Daily Cap**: A configurable maximum number of emails or calls the system may send per 24-hour period
- **Approval Queue**: A holding area where generated outreach content awaits operator review before sending
- **Public Business Source**: Legitimate business directories or company websites where contact information is publicly listed (e.g., Google Maps, JustDial, IndiaMART, Yelp, LinkedIn Company pages)
- **Business Email**: An email address associated with a business domain or role-based address (e.g., info@, contact@, sales@), excluding personal email providers
- **Call Flow**: The programmed sequence of TTS prompts, ASR listening, and branching logic during a voice call
- **Dry-run Mode**: A testing mode where the system simulates outreach without actually sending emails or making calls
- **Compliance**: Adherence to CAN-SPAM, TRAI, GDPR, and other applicable regulations governing commercial communications

## Requirements

### Requirement 1

**User Story:** As a system operator, I want the system to only scrape business contact information from approved public sources, so that I comply with privacy laws and avoid contacting private individuals.

#### Acceptance Criteria

1. WHEN the scraper module executes, THE System SHALL retrieve contact information exclusively from configured public business sources including Google Maps Places API, JustDial, IndiaMART, Yelp, and public LinkedIn Company pages
2. WHEN the scraper encounters a data source, THE System SHALL verify the source is in the approved public business sources list before extracting any contact information
3. WHEN the scraper processes contact information, THE System SHALL reject and discard any leads sourced from personal social media profiles, purchased contact lists, or non-public directories
4. WHEN duplicate leads are detected based on business name, website, and phone number combination, THE System SHALL merge or discard duplicates to maintain a single record per business
5. WHEN the scraper accesses external websites, THE System SHALL respect robots.txt directives and implement configurable crawl delays with exponential backoff on rate limit responses

### Requirement 2

**User Story:** As a system operator, I want all leads to be verified for email deliverability and phone validity, so that outreach efforts target legitimate business contacts and maintain sender reputation.

#### Acceptance Criteria

1. WHEN a lead is processed for verification, THE System SHALL validate the email address using a third-party verification provider (AbstractAPI, ZeroBounce, or Hunter) and receive a deliverability classification
2. WHEN an email verification result indicates the address is undeliverable or classified as a personal email provider (gmail, yahoo, hotmail), THE System SHALL mark the lead as unverified and exclude it from outreach campaigns
3. WHEN a lead contains a phone number, THE System SHALL validate the number using Twilio Lookup or NumVerify to confirm validity and carrier type
4. WHEN phone verification returns a confidence score below the configured threshold or indicates a non-business line, THE System SHALL flag the lead for manual review or exclusion
5. WHEN verification is complete, THE System SHALL persist verification results including confidence scores, provider responses, and timestamps to the database

### Requirement 3

**User Story:** As a business contact, I want to easily unsubscribe from communications, so that I can stop receiving unwanted emails and calls immediately.

#### Acceptance Criteria

1. WHEN the system generates an outreach email, THE System SHALL include a clearly visible unsubscribe link with unique tracking parameters for the recipient
2. WHEN a recipient clicks the unsubscribe link, THE System SHALL immediately mark the contact as opted-out in the database and display a confirmation page
3. WHEN an opted-out contact is encountered during campaign execution, THE System SHALL skip the contact and never send emails or make calls to that contact again
4. WHEN a recipient replies to an email with unsubscribe keywords (unsubscribe, stop, remove, opt-out), THE System SHALL detect the keywords and automatically mark the contact as opted-out
5. WHEN a call recipient requests to be removed during a voice call or via SMS reply with "STOP", THE System SHALL immediately update the opt-out status and terminate the call flow

### Requirement 4

**User Story:** As a system operator, I want configurable daily caps and rate limits on outreach, so that I can control sending volume and avoid being flagged as spam.

#### Acceptance Criteria

1. WHEN the scheduler executes a daily outreach campaign, THE System SHALL enforce a configurable daily email cap (default 100 emails per 24-hour period) and halt sending when the cap is reached
2. WHEN the scheduler executes voice call campaigns, THE System SHALL enforce a configurable daily call cap (default 100 calls per 24-hour period) and halt calling when the cap is reached
3. WHEN sending emails to multiple recipients at the same domain, THE System SHALL throttle sending to a maximum of 5 emails per hour per domain to avoid domain-level rate limiting
4. WHEN making calls to a specific country or region, THE System SHALL enforce per-country call caps to comply with local regulations and avoid abuse
5. WHEN a lead has been contacted, THE System SHALL enforce a cooldown period (default 30 days) before allowing the same business to be contacted again

### Requirement 5

**User Story:** As a system operator, I want to review and approve outreach content before it is sent, so that I can ensure quality and compliance for initial campaigns.

#### Acceptance Criteria

1. WHEN approval mode is enabled in configuration, THE System SHALL place all generated outreach content into an approval queue before sending
2. WHEN an operator accesses the approval queue, THE System SHALL display the generated email content, personalization details, and lead information for review
3. WHEN an operator approves queued content, THE System SHALL move the approved items to the sending queue and proceed with outreach
4. WHEN an operator rejects or edits queued content, THE System SHALL save the modifications and allow re-approval before sending
5. WHERE approval mode is disabled, THE System SHALL bypass the approval queue and send outreach content automatically after generation

### Requirement 6

**User Story:** As a system operator, I want the system to comply with CAN-SPAM, TRAI, and GDPR regulations, so that DevSync Innovation avoids legal penalties and maintains ethical business practices.

#### Acceptance Criteria

1. WHEN the system generates an outreach email, THE System SHALL include the sender's valid physical business address, clear business identity (DevSync Innovation), and a functional unsubscribe mechanism
2. WHEN processing personal data, THE System SHALL store only the minimum necessary information (business name, contact details, verification status, outreach history) and avoid collecting sensitive personal information
3. WHEN the configured data retention period expires (default 90 days), THE System SHALL automatically purge outreach logs and non-essential lead data while preserving opt-out records indefinitely
4. WHEN making voice calls, THE System SHALL check the lead's phone number against configured Do Not Call registry lists and skip contacts that appear on such lists
5. WHEN a data subject requests access to their stored information, THE System SHALL provide an API endpoint or manual process for operators to retrieve and export the requested data

### Requirement 7

**User Story:** As a system operator, I want comprehensive logging of all outreach attempts, so that I can audit system behavior and investigate issues.

#### Acceptance Criteria

1. WHEN the system attempts to send an email, THE System SHALL log the timestamp, lead identifier, email content hash, delivery status, and provider response to the audit log
2. WHEN the system makes a voice call, THE System SHALL log the timestamp, lead identifier, call duration, call outcome (answered, voicemail, busy, no-answer), and transcript or recording reference
3. WHEN a third-party API call fails, THE System SHALL log the error details, retry attempts, and final resolution status
4. WHEN the configured log retention period expires, THE System SHALL archive or delete logs according to the retention policy while preserving compliance-required records
5. WHEN critical errors occur (repeated API failures, database connection loss, daily cap exceeded), THE System SHALL generate alerts and notify operators via configured channels

### Requirement 8

**User Story:** As a lead scraper module, I want to extract business information from multiple public sources, so that the system has a diverse pool of potential leads.

#### Acceptance Criteria

1. WHEN the Google Maps scraper executes, THE System SHALL query the Google Maps Places API with configured search parameters (location, business category) and extract business name, address, phone numbers, website, and category
2. WHEN the JustDial scraper executes, THE System SHALL perform HTTP requests to JustDial search pages, parse HTML responses to extract business listings, and respect rate limits with exponential backoff
3. WHEN the LinkedIn Company scraper executes, THE System SHALL access public LinkedIn Company pages via official APIs or permitted methods and extract company name, website, and publicly listed contact information
4. WHEN any scraper encounters an error or rate limit response (HTTP 429, 503), THE System SHALL implement exponential backoff with jitter and retry up to 3 times before marking the source as temporarily unavailable
5. WHEN scraped data is received, THE System SHALL normalize the data into a standardized lead object format with fields for source, business_name, city, category, website, phone_numbers, emails, and raw_metadata

### Requirement 9

**User Story:** As an email outreach module, I want to generate personalized email content using AI, so that outreach messages are relevant and engaging to recipients.

#### Acceptance Criteria

1. WHEN a verified lead is selected for email outreach, THE System SHALL call the configured AI provider (OpenAI or AIMLAPI) with lead context (business name, category, city) to generate a personalized 3-line email
2. WHEN the AI generates email content, THE System SHALL validate that the content includes a personalized hook, a clear value proposition mentioning DevSync Innovation's services, and a call-to-action
3. WHEN AI content generation fails or times out, THE System SHALL fall back to a pre-configured template with variable substitution for business name, category, and city
4. WHEN email content is finalized, THE System SHALL append required compliance elements (sender identity, physical address, unsubscribe link) to the email body
5. WHEN the email is ready to send, THE System SHALL persist the complete email content to the database before transmission for audit purposes

### Requirement 10

**User Story:** As an email sender module, I want to reliably deliver emails through a reputable provider with proper authentication, so that emails reach recipients' inboxes and maintain sender reputation.

#### Acceptance Criteria

1. WHEN the system sends an email, THE System SHALL use a configured email provider (SendGrid, Mailgun, or authenticated SMTP) with valid SPF, DKIM, and DMARC records configured for the sending domain
2. WHEN an email send request fails with a transient error (rate limit, temporary server error), THE System SHALL retry the request using exponential backoff with a maximum of 3 retry attempts
3. WHEN an email send request fails with a permanent error (invalid recipient, blocked domain), THE System SHALL mark the lead as undeliverable and exclude it from future campaigns
4. WHEN the email provider sends a webhook notification (bounce, complaint, unsubscribe), THE System SHALL process the webhook, update the lead status accordingly, and honor opt-out requests immediately
5. WHEN sending multiple emails to the same domain, THE System SHALL enforce per-domain throttling limits to avoid triggering recipient server rate limits

### Requirement 11

**User Story:** As a voice call module, I want to conduct automated calls with text-to-speech and speech recognition, so that the system can engage with business contacts via phone.

#### Acceptance Criteria

1. WHEN the system initiates a voice call, THE System SHALL use the configured telephony provider (Twilio or Exotel) to place the call to the verified business phone number
2. WHEN a call is answered, THE System SHALL play a TTS introduction message identifying the caller as DevSync Innovation and stating the purpose of the call
3. WHEN the call recipient responds, THE System SHALL use ASR (Automatic Speech Recognition) to detect intent keywords (interested, not interested, talk to human, call back later, remove from list)
4. WHEN voicemail is detected, THE System SHALL leave a brief pre-recorded message and mark the lead for no further calls for a configurable period (default 7 days)
5. WHEN a call completes, THE System SHALL store the call outcome, duration, transcript (if available), and recording reference (if consent obtained) to the database

### Requirement 12

**User Story:** As a scheduler service, I want to execute daily outreach campaigns at configured times, so that leads are contacted consistently and within appropriate business hours.

#### Acceptance Criteria

1. WHEN the configured email send time is reached (default 10:00 IST), THE System SHALL retrieve up to the daily email cap of verified, non-opted-out leads from the database and initiate email sending
2. WHEN the configured call window begins (default 11:00 IST), THE System SHALL retrieve up to the daily call cap of verified, non-opted-out leads and distribute calls evenly across the call window (default 11:00-17:00 IST)
3. WHEN selecting leads for outreach, THE System SHALL exclude leads contacted within the cooldown period (default 30 days) and prioritize leads that have never been contacted
4. WHEN the daily campaign completes, THE System SHALL generate a summary report including total emails sent, total calls made, success rates, errors encountered, and send it to configured operator email addresses
5. WHEN the scheduler encounters a critical error (database unavailable, all API providers failing), THE System SHALL halt the campaign, log the error, and alert operators without retrying until the issue is resolved

### Requirement 13

**User Story:** As a system operator, I want a dashboard to review leads, approve content, and monitor campaign performance, so that I can maintain control and visibility over outreach activities.

#### Acceptance Criteria

1. WHEN an operator accesses the dashboard, THE System SHALL display an overview of campaign statistics including total leads, verified leads, emails sent today, calls made today, and opt-out count
2. WHEN approval mode is enabled, THE System SHALL display the approval queue with pending outreach items showing lead details, generated content, and approve/reject/edit actions
3. WHEN an operator views the outreach history, THE System SHALL display a paginated list of recent emails and calls with timestamps, lead information, status, and outcome
4. WHEN an operator searches for a specific lead, THE System SHALL provide search functionality by business name, email, phone number, or city and display matching results
5. WHEN an operator manually blacklists a contact, THE System SHALL provide a blacklist management interface to add contacts to the opt-out list and prevent future outreach

### Requirement 14

**User Story:** As a system operator, I want the system to operate in dry-run mode for testing, so that I can validate configuration and behavior without sending real emails or making real calls.

#### Acceptance Criteria

1. WHEN dry-run mode is enabled in configuration, THE System SHALL execute all campaign logic including lead selection, verification, and content generation without actually sending emails or placing calls
2. WHEN dry-run mode is active, THE System SHALL log all actions that would have been taken (email would be sent to X, call would be placed to Y) to allow operator review
3. WHEN dry-run mode is active, THE System SHALL still enforce daily caps and rate limits to accurately simulate production behavior
4. WHEN an operator disables dry-run mode, THE System SHALL require explicit confirmation and display a warning about transitioning to live outreach
5. WHERE dry-run mode is disabled, THE System SHALL execute all outreach actions normally and send real emails and place real calls

### Requirement 15

**User Story:** As a system administrator, I want proper database schema and storage for all system entities, so that data is organized, queryable, and persistent.

#### Acceptance Criteria

1. WHEN the system initializes, THE System SHALL create or migrate database tables for leads, outreach_history, opt_outs, verification_results, and audit_logs
2. WHEN a lead is stored, THE System SHALL persist all required fields (source, business_name, city, category, website, phone_numbers, emails, verification_status, created_at, updated_at)
3. WHEN an outreach attempt is recorded, THE System SHALL store the lead_id, outreach_type (email or call), timestamp, status, content_hash, provider_response, and outcome
4. WHEN an opt-out is recorded, THE System SHALL store the contact identifier (email or phone), opt_out_timestamp, opt_out_method (link click, email reply, call request, SMS), and ensure the record is never deleted
5. WHEN querying leads for campaigns, THE System SHALL use database indexes on frequently queried fields (verification_status, last_contacted_at, opt_out_status) to ensure performant queries

### Requirement 16

**User Story:** As a system operator, I want proper error handling and retry logic for API failures, so that transient issues do not cause campaign failures.

#### Acceptance Criteria

1. WHEN a third-party API call fails with a transient error (timeout, 5xx server error, rate limit), THE System SHALL retry the request using exponential backoff with jitter
2. WHEN retry attempts are exhausted (default maximum 3 retries), THE System SHALL log the failure, mark the affected lead or action as failed, and continue processing other items
3. WHEN a critical API provider is consistently failing (circuit breaker threshold reached), THE System SHALL temporarily disable that provider, alert operators, and attempt to use fallback providers if configured
4. WHEN network connectivity is lost, THE System SHALL detect the condition, pause outreach operations, and resume automatically when connectivity is restored
5. WHEN database connection is lost, THE System SHALL attempt to reconnect with exponential backoff and queue pending operations in memory until the connection is restored or a timeout is reached

### Requirement 17

**User Story:** As a system operator, I want comprehensive configuration management via environment variables, so that I can deploy and configure the system without code changes.

#### Acceptance Criteria

1. WHEN the system starts, THE System SHALL load all configuration from environment variables including database connection, API credentials, daily caps, timezone, and operational modes
2. WHEN a required environment variable is missing, THE System SHALL fail to start and display a clear error message indicating which variable is required
3. WHEN configuration values are invalid (negative daily cap, invalid timezone), THE System SHALL validate the values at startup and fail with descriptive error messages
4. WHEN sensitive configuration values (API keys, database passwords) are logged, THE System SHALL mask or redact the values to prevent credential exposure
5. WHERE optional configuration is not provided, THE System SHALL use documented default values (daily caps of 100, approval mode enabled, dry-run mode enabled, 30-day cooldown)

### Requirement 18

**User Story:** As a system operator, I want the system to default to safe settings on first deployment, so that I cannot accidentally send mass outreach before proper configuration and testing.

#### Acceptance Criteria

1. WHEN the system is deployed for the first time, THE System SHALL default to dry-run mode enabled, approval mode enabled, and low daily caps (10 emails, 10 calls)
2. WHEN an operator attempts to disable dry-run mode, THE System SHALL display a prominent warning about legal compliance responsibilities and require explicit confirmation
3. WHEN an operator attempts to increase daily caps above 100, THE System SHALL display a warning about sender reputation and rate limiting risks
4. WHEN the system detects it is running in production environment, THE System SHALL require that SPF, DKIM, and DMARC records are configured before allowing email sending
5. WHEN approval mode is disabled for the first time, THE System SHALL require operator acknowledgment that they will monitor outreach quality and compliance
