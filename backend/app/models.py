"""Database models and Pydantic schemas."""

from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, Text,
    ForeignKey, Index, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator
from enum import Enum

from app.db import Base


# ============================================================================
# SQLAlchemy ORM Models
# ============================================================================

class Lead(Base):
    """Lead model - represents a business contact."""
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, index=True)
    business_name = Column(String(255), nullable=False)
    city = Column(String(100))
    category = Column(String(100), index=True)
    website = Column(String(500))
    primary_email = Column(String(255), index=True)
    primary_phone = Column(String(20), index=True)
    raw_metadata = Column(JSON, default={})
    
    # Verification status
    email_verified = Column(Boolean, default=False, index=True)
    phone_verified = Column(Boolean, default=False, index=True)
    verification_confidence = Column(Float)
    
    # Opt-out status
    opted_out = Column(Boolean, default=False, index=True)
    opted_out_at = Column(DateTime)
    opted_out_method = Column(String(50))
    
    # Contact tracking
    last_contacted_at = Column(DateTime, index=True)
    contact_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    verification_results = relationship("VerificationResult", back_populates="lead", cascade="all, delete-orphan")
    outreach_history = relationship("OutreachHistory", back_populates="lead", cascade="all, delete-orphan")
    
    # Unique constraint for deduplication
    __table_args__ = (
        UniqueConstraint('business_name', 'website', 'primary_phone', name='uix_lead_identity'),
        Index('idx_leads_verified_opted_out', 'email_verified', 'phone_verified', 'opted_out'),
        Index('idx_leads_last_contacted', 'last_contacted_at'),
    )


class VerificationResult(Base):
    """Verification result model - stores email/phone verification details."""
    __tablename__ = "verification_results"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id', ondelete='CASCADE'), nullable=False, index=True)
    verification_type = Column(String(20), nullable=False)  # 'email' or 'phone'
    contact_value = Column(String(255), nullable=False)
    is_valid = Column(Boolean, nullable=False)
    confidence_score = Column(Float)
    provider_name = Column(String(50))
    provider_response = Column(JSON, default={})
    verified_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationship
    lead = relationship("Lead", back_populates="verification_results")
    
    __table_args__ = (
        Index('idx_verification_lead', 'lead_id'),
        Index('idx_verification_type_value', 'verification_type', 'contact_value'),
    )


class OutreachHistory(Base):
    """Outreach history model - tracks all email and call attempts."""
    __tablename__ = "outreach_history"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id', ondelete='CASCADE'), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), index=True)
    outreach_type = Column(String(20), nullable=False)  # 'email' or 'call'
    content_hash = Column(String(64))  # SHA256 hash of content
    status = Column(String(50), nullable=False)  # 'sent', 'delivered', 'bounced', 'failed'
    provider_message_id = Column(String(255))
    provider_response = Column(JSON, default={})
    
    # Call-specific fields
    outcome = Column(String(50))  # 'answered', 'voicemail', 'busy', 'no-answer'
    duration_seconds = Column(Integer)
    transcript = Column(Text)
    recording_url = Column(String(500))
    
    # Timestamps
    attempted_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    completed_at = Column(DateTime)
    
    # Relationships
    lead = relationship("Lead", back_populates="outreach_history")
    campaign = relationship("Campaign", back_populates="outreach_attempts")
    
    __table_args__ = (
        Index('idx_outreach_lead', 'lead_id'),
        Index('idx_outreach_campaign', 'campaign_id'),
        Index('idx_outreach_attempted', 'attempted_at'),
        Index('idx_outreach_type_status', 'outreach_type', 'status'),
    )


class OptOut(Base):
    """Opt-out model - permanently stores opt-out requests."""
    __tablename__ = "opt_outs"
    
    id = Column(Integer, primary_key=True, index=True)
    contact_type = Column(String(20), nullable=False)  # 'email' or 'phone'
    contact_value = Column(String(255), nullable=False, unique=True, index=True)
    opt_out_method = Column(String(50))  # 'link', 'email_reply', 'call_request', 'sms'
    opted_out_at = Column(DateTime, default=func.now(), nullable=False)
    source_lead_id = Column(Integer, ForeignKey('leads.id'))
    
    __table_args__ = (
        Index('idx_optouts_contact', 'contact_type', 'contact_value'),
    )


class ApprovalQueue(Base):
    """Approval queue model - holds outreach content pending approval."""
    __tablename__ = "approval_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id', ondelete='CASCADE'), nullable=False, index=True)
    outreach_type = Column(String(20), nullable=False)  # 'email' or 'call'
    content = Column(JSON, nullable=False)  # Stores email/call content
    status = Column(String(20), default='pending', index=True)  # 'pending', 'approved', 'rejected', 'sent'
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)  # Auto-expire after 7 days
    
    # Relationship
    lead = relationship("Lead")
    
    __table_args__ = (
        Index('idx_approval_status', 'status', 'created_at'),
    )


class Campaign(Base):
    """Campaign model - tracks daily outreach campaigns."""
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_type = Column(String(20), nullable=False)  # 'email' or 'call'
    total_attempted = Column(Integer, default=0)
    total_success = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    errors = Column(JSON, default=[])
    started_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime)
    
    # Relationship
    outreach_attempts = relationship("OutreachHistory", back_populates="campaign")
    
    __table_args__ = (
        Index('idx_campaign_type_started', 'campaign_type', 'started_at'),
    )


class AuditLog(Base):
    """Audit log model - comprehensive logging of all system actions."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    log_level = Column(String(20), nullable=False)  # 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    component = Column(String(50), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    lead_id = Column(Integer)
    user_id = Column(String(100))
    details = Column(JSON, default={})
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    
    __table_args__ = (
        Index('idx_audit_created', 'created_at'),
        Index('idx_audit_component_action', 'component', 'action'),
    )


# ============================================================================
# Pydantic Schemas for API
# ============================================================================

class LeadBase(BaseModel):
    """Base lead schema."""
    source: str = Field(..., min_length=1, max_length=50)
    business_name: str = Field(..., min_length=1, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=500)
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = Field(None, max_length=20)
    
    @validator('source')
    def validate_source(cls, v):
        """Validate source is from approved list."""
        approved_sources = ["google_maps", "justdial", "indiamart", "yelp", "linkedin_company"]
        if v not in approved_sources:
            raise ValueError(f"Source must be one of: {', '.join(approved_sources)}")
        return v


class LeadCreate(LeadBase):
    """Schema for creating a lead."""
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""
    business_name: Optional[str] = Field(None, min_length=1, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=500)
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = Field(None, max_length=20)
    email_verified: Optional[bool] = None
    phone_verified: Optional[bool] = None
    opted_out: Optional[bool] = None


class LeadResponse(LeadBase):
    """Schema for lead response."""
    id: int
    email_verified: bool
    phone_verified: bool
    verification_confidence: Optional[float]
    opted_out: bool
    opted_out_at: Optional[datetime]
    last_contacted_at: Optional[datetime]
    contact_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class VerificationResultCreate(BaseModel):
    """Schema for creating verification result."""
    lead_id: int
    verification_type: str = Field(..., pattern="^(email|phone)$")
    contact_value: str
    is_valid: bool
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    provider_name: str
    provider_response: Dict[str, Any] = Field(default_factory=dict)


class VerificationResultResponse(BaseModel):
    """Schema for verification result response."""
    id: int
    lead_id: int
    verification_type: str
    contact_value: str
    is_valid: bool
    confidence_score: Optional[float]
    provider_name: str
    verified_at: datetime
    
    class Config:
        from_attributes = True


class OutreachHistoryCreate(BaseModel):
    """Schema for creating outreach history."""
    lead_id: int
    campaign_id: Optional[int] = None
    outreach_type: str = Field(..., pattern="^(email|call)$")
    content_hash: Optional[str] = Field(None, max_length=64)
    status: str
    provider_message_id: Optional[str] = None
    provider_response: Dict[str, Any] = Field(default_factory=dict)
    outcome: Optional[str] = None
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    recording_url: Optional[str] = None


class OutreachHistoryResponse(BaseModel):
    """Schema for outreach history response."""
    id: int
    lead_id: int
    campaign_id: Optional[int]
    outreach_type: str
    status: str
    outcome: Optional[str]
    duration_seconds: Optional[int]
    attempted_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class OptOutCreate(BaseModel):
    """Schema for creating opt-out."""
    contact_type: str = Field(..., pattern="^(email|phone)$")
    contact_value: str
    opt_out_method: str
    source_lead_id: Optional[int] = None


class OptOutResponse(BaseModel):
    """Schema for opt-out response."""
    id: int
    contact_type: str
    contact_value: str
    opt_out_method: str
    opted_out_at: datetime
    
    class Config:
        from_attributes = True


class ApprovalQueueCreate(BaseModel):
    """Schema for creating approval queue item."""
    lead_id: int
    outreach_type: str = Field(..., pattern="^(email|call)$")
    content: Dict[str, Any]
    expires_at: datetime


class ApprovalQueueResponse(BaseModel):
    """Schema for approval queue response."""
    id: int
    lead_id: int
    outreach_type: str
    content: Dict[str, Any]
    status: str
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime
    expires_at: datetime
    
    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    """Schema for creating campaign."""
    campaign_type: str = Field(..., pattern="^(email|call)$")


class CampaignResponse(BaseModel):
    """Schema for campaign response."""
    id: int
    campaign_type: str
    total_attempted: int
    total_success: int
    total_failed: int
    started_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AuditLogCreate(BaseModel):
    """Schema for creating audit log."""
    log_level: str
    component: str
    action: str
    lead_id: Optional[int] = None
    user_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""
    id: int
    log_level: str
    component: str
    action: str
    lead_id: Optional[int]
    user_id: Optional[str]
    details: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Enums
# ============================================================================

class OutreachType(str, Enum):
    """Outreach type enum."""
    EMAIL = "email"
    CALL = "call"


class OutreachStatus(str, Enum):
    """Outreach status enum."""
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


class CallOutcome(str, Enum):
    """Call outcome enum."""
    ANSWERED = "answered"
    VOICEMAIL = "voicemail"
    BUSY = "busy"
    NO_ANSWER = "no-answer"


class ApprovalStatus(str, Enum):
    """Approval status enum."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
