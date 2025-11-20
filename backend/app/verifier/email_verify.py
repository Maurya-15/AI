"""Email verification using AbstractAPI/ZeroBounce/Hunter."""

import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class EmailVerificationResult:
    """Email verification result."""
    email: str
    is_deliverable: bool
    is_business: bool
    confidence_score: float
    provider_response: Dict[str, Any]
    verified_at: datetime


class EmailVerifier:
    """Email verification service."""
    
    # Personal email providers to flag
    PERSONAL_PROVIDERS = [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'live.com', 'aol.com', 'icloud.com', 'mail.com',
        'protonmail.com', 'yandex.com', 'zoho.com'
    ]
    
    # Role-based emails that are acceptable for business
    BUSINESS_ROLES = [
        'info', 'contact', 'sales', 'support', 'admin',
        'hello', 'team', 'office', 'enquiry', 'inquiry'
    ]
    
    def __init__(self):
        """Initialize email verifier."""
        self.settings = get_settings()
        self.cache: Dict[str, EmailVerificationResult] = {}
        self.cache_ttl = timedelta(days=30)
    
    async def verify(self, email: str) -> EmailVerificationResult:
        """
        Verify email deliverability and type.
        
        Args:
            email: Email address to verify
            
        Returns:
            EmailVerificationResult
        """
        # Check cache first
        if email in self.cache:
            cached = self.cache[email]
            if datetime.utcnow() - cached.verified_at < self.cache_ttl:
                logger.debug(f"Using cached verification for {email}")
                return cached
        
        # Try providers in order of preference
        result = None
        
        if self.settings.ABSTRACTAPI_KEY:
            result = await self._verify_with_abstractapi(email)
        elif self.settings.ZEROBOUNCE_API_KEY:
            result = await self._verify_with_zerobounce(email)
        elif self.settings.HUNTER_API_KEY:
            result = await self._verify_with_hunter(email)
        else:
            # Fallback to basic validation
            result = self._basic_verification(email)
        
        # Cache result
        if result:
            self.cache[email] = result
        
        return result
    
    async def _verify_with_abstractapi(self, email: str) -> EmailVerificationResult:
        """
        Verify email using AbstractAPI.
        
        Args:
            email: Email address
            
        Returns:
            EmailVerificationResult
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://emailvalidation.abstractapi.com/v1/",
                    params={
                        "api_key": self.settings.ABSTRACTAPI_KEY,
                        "email": email
                    },
                    timeout=10.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Parse AbstractAPI response
                is_deliverable = (
                    data.get("deliverability") == "DELIVERABLE" and
                    data.get("is_valid_format", {}).get("value", False) and
                    not data.get("is_disposable_email", {}).get("value", False)
                )
                
                # Check if business email
                domain = email.split('@')[1].lower() if '@' in email else ''
                is_business = (
                    domain not in self.PERSONAL_PROVIDERS or
                    self._is_role_based_email(email)
                )
                
                # Calculate confidence score
                confidence = self._calculate_confidence(data, is_deliverable, is_business)
                
                return EmailVerificationResult(
                    email=email,
                    is_deliverable=is_deliverable,
                    is_business=is_business,
                    confidence_score=confidence,
                    provider_response=data,
                    verified_at=datetime.utcnow()
                )
        
        except Exception as e:
            logger.error(f"AbstractAPI verification failed for {email}: {e}")
            return self._basic_verification(email)
    
    async def _verify_with_zerobounce(self, email: str) -> EmailVerificationResult:
        """
        Verify email using ZeroBounce.
        
        Args:
            email: Email address
            
        Returns:
            EmailVerificationResult
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.zerobounce.net/v2/validate",
                    params={
                        "api_key": self.settings.ZEROBOUNCE_API_KEY,
                        "email": email
                    },
                    timeout=10.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Parse ZeroBounce response
                status = data.get("status", "").lower()
                is_deliverable = status in ["valid", "catch-all"]
                
                # Check if business email
                domain = email.split('@')[1].lower() if '@' in email else ''
                is_business = (
                    domain not in self.PERSONAL_PROVIDERS or
                    self._is_role_based_email(email)
                )
                
                # Calculate confidence
                confidence = 0.9 if status == "valid" else 0.6 if status == "catch-all" else 0.0
                if not is_business:
                    confidence *= 0.5
                
                return EmailVerificationResult(
                    email=email,
                    is_deliverable=is_deliverable,
                    is_business=is_business,
                    confidence_score=confidence,
                    provider_response=data,
                    verified_at=datetime.utcnow()
                )
        
        except Exception as e:
            logger.error(f"ZeroBounce verification failed for {email}: {e}")
            return self._basic_verification(email)
    
    async def _verify_with_hunter(self, email: str) -> EmailVerificationResult:
        """
        Verify email using Hunter.io.
        
        Args:
            email: Email address
            
        Returns:
            EmailVerificationResult
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.hunter.io/v2/email-verifier",
                    params={
                        "api_key": self.settings.HUNTER_API_KEY,
                        "email": email
                    },
                    timeout=10.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Parse Hunter response
                result = data.get("data", {})
                status = result.get("status", "").lower()
                is_deliverable = status in ["valid", "accept_all"]
                
                # Check if business email
                domain = email.split('@')[1].lower() if '@' in email else ''
                is_business = (
                    domain not in self.PERSONAL_PROVIDERS or
                    self._is_role_based_email(email)
                )
                
                # Use Hunter's score
                confidence = result.get("score", 0) / 100.0
                if not is_business:
                    confidence *= 0.5
                
                return EmailVerificationResult(
                    email=email,
                    is_deliverable=is_deliverable,
                    is_business=is_business,
                    confidence_score=confidence,
                    provider_response=data,
                    verified_at=datetime.utcnow()
                )
        
        except Exception as e:
            logger.error(f"Hunter verification failed for {email}: {e}")
            return self._basic_verification(email)
    
    def _basic_verification(self, email: str) -> EmailVerificationResult:
        """
        Basic email verification without external API.
        
        Args:
            email: Email address
            
        Returns:
            EmailVerificationResult
        """
        import re
        
        # Basic format validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_valid_format = bool(re.match(pattern, email))
        
        # Check if business email
        domain = email.split('@')[1].lower() if '@' in email else ''
        is_business = (
            domain not in self.PERSONAL_PROVIDERS or
            self._is_role_based_email(email)
        )
        
        # Low confidence for basic validation
        confidence = 0.5 if is_valid_format and is_business else 0.3
        
        return EmailVerificationResult(
            email=email,
            is_deliverable=is_valid_format,
            is_business=is_business,
            confidence_score=confidence,
            provider_response={"method": "basic_validation"},
            verified_at=datetime.utcnow()
        )
    
    def _is_role_based_email(self, email: str) -> bool:
        """
        Check if email is role-based (acceptable for business).
        
        Args:
            email: Email address
            
        Returns:
            True if role-based
        """
        local_part = email.split('@')[0].lower() if '@' in email else ''
        return any(role in local_part for role in self.BUSINESS_ROLES)
    
    def _calculate_confidence(
        self,
        data: Dict[str, Any],
        is_deliverable: bool,
        is_business: bool
    ) -> float:
        """
        Calculate confidence score from provider data.
        
        Args:
            data: Provider response data
            is_deliverable: Whether email is deliverable
            is_business: Whether email is business
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.0
        
        if is_deliverable:
            confidence += 0.5
        
        if is_business:
            confidence += 0.3
        
        # Adjust based on quality score if available
        if data.get("quality_score"):
            confidence += data["quality_score"] * 0.2
        
        # Penalize if disposable
        if data.get("is_disposable_email", {}).get("value", False):
            confidence *= 0.5
        
        # Penalize if free provider (personal)
        if data.get("is_free_email", {}).get("value", False) and not self._is_role_based_email(data.get("email", "")):
            confidence *= 0.6
        
        return min(confidence, 1.0)
    
    def meets_threshold(self, result: EmailVerificationResult) -> bool:
        """
        Check if verification result meets confidence threshold.
        
        Args:
            result: Verification result
            
        Returns:
            True if meets threshold
        """
        threshold = self.settings.EMAIL_VERIFICATION_CONFIDENCE_THRESHOLD
        return result.confidence_score >= threshold and result.is_deliverable and result.is_business
