"""Phone verification using Twilio Lookup/NumVerify."""

import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import phonenumbers

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class PhoneVerificationResult:
    """Phone verification result."""
    phone: str
    is_valid: bool
    carrier_type: str  # landline, mobile, voip
    is_business_line: bool
    confidence_score: float
    provider_response: Dict[str, Any]
    verified_at: datetime


class PhoneVerifier:
    """Phone verification service."""
    
    def __init__(self):
        """Initialize phone verifier."""
        self.settings = get_settings()
        self.cache: Dict[str, PhoneVerificationResult] = {}
        self.cache_ttl = timedelta(days=30)
    
    async def verify(self, phone: str, country_code: str = "IN") -> PhoneVerificationResult:
        """
        Verify phone validity and carrier type.
        
        Args:
            phone: Phone number to verify
            country_code: ISO country code (default: IN)
            
        Returns:
            PhoneVerificationResult
        """
        # Normalize phone first
        try:
            parsed = phonenumbers.parse(phone, country_code)
            normalized = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception as e:
            logger.debug(f"Failed to parse phone {phone}: {e}")
            return self._invalid_result(phone)
        
        # Check cache
        if normalized in self.cache:
            cached = self.cache[normalized]
            if datetime.utcnow() - cached.verified_at < self.cache_ttl:
                logger.debug(f"Using cached verification for {normalized}")
                return cached
        
        # Try providers in order
        result = None
        
        if self.settings.TWILIO_ACCOUNT_SID and self.settings.TWILIO_AUTH_TOKEN:
            result = await self._verify_with_twilio(normalized)
        elif self.settings.NUMVERIFY_KEY:
            result = await self._verify_with_numverify(normalized)
        else:
            # Fallback to basic validation
            result = self._basic_verification(normalized)
        
        # Cache result
        if result:
            self.cache[normalized] = result
        
        return result
    
    async def _verify_with_twilio(self, phone: str) -> PhoneVerificationResult:
        """
        Verify phone using Twilio Lookup API.
        
        Args:
            phone: Phone number in E.164 format
            
        Returns:
            PhoneVerificationResult
        """
        try:
            async with httpx.AsyncClient() as client:
                # Twilio Lookup API
                url = f"https://lookups.twilio.com/v1/PhoneNumbers/{phone}"
                
                response = await client.get(
                    url,
                    params={"Type": "carrier"},
                    auth=(
                        self.settings.TWILIO_ACCOUNT_SID,
                        self.settings.TWILIO_AUTH_TOKEN
                    ),
                    timeout=10.0
                )
                
                if response.status_code == 404:
                    # Phone not found
                    return self._invalid_result(phone)
                
                response.raise_for_status()
                data = response.json()
                
                # Parse Twilio response
                carrier = data.get("carrier", {})
                carrier_type = carrier.get("type", "unknown").lower()
                
                # Determine if business line
                # Landlines and VOIP are more likely business
                is_business_line = carrier_type in ["landline", "voip"]
                
                # Calculate confidence
                confidence = self._calculate_confidence_twilio(data, carrier_type)
                
                return PhoneVerificationResult(
                    phone=phone,
                    is_valid=True,
                    carrier_type=carrier_type,
                    is_business_line=is_business_line,
                    confidence_score=confidence,
                    provider_response=data,
                    verified_at=datetime.utcnow()
                )
        
        except Exception as e:
            logger.error(f"Twilio verification failed for {phone}: {e}")
            return self._basic_verification(phone)
    
    async def _verify_with_numverify(self, phone: str) -> PhoneVerificationResult:
        """
        Verify phone using NumVerify API.
        
        Args:
            phone: Phone number in E.164 format
            
        Returns:
            PhoneVerificationResult
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://apilayer.net/api/validate",
                    params={
                        "access_key": self.settings.NUMVERIFY_KEY,
                        "number": phone,
                        "format": 1
                    },
                    timeout=10.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Parse NumVerify response
                is_valid = data.get("valid", False)
                
                if not is_valid:
                    return self._invalid_result(phone)
                
                # NumVerify provides line_type
                line_type = data.get("line_type", "unknown").lower()
                carrier_type = self._map_line_type(line_type)
                
                # Determine if business line
                is_business_line = carrier_type in ["landline", "voip"]
                
                # Calculate confidence
                confidence = 0.8 if is_valid else 0.0
                if is_business_line:
                    confidence += 0.1
                
                return PhoneVerificationResult(
                    phone=phone,
                    is_valid=is_valid,
                    carrier_type=carrier_type,
                    is_business_line=is_business_line,
                    confidence_score=min(confidence, 1.0),
                    provider_response=data,
                    verified_at=datetime.utcnow()
                )
        
        except Exception as e:
            logger.error(f"NumVerify verification failed for {phone}: {e}")
            return self._basic_verification(phone)
    
    def _basic_verification(self, phone: str) -> PhoneVerificationResult:
        """
        Basic phone verification using phonenumbers library.
        
        Args:
            phone: Phone number
            
        Returns:
            PhoneVerificationResult
        """
        try:
            # Parse and validate
            parsed = phonenumbers.parse(phone, None)
            is_valid = phonenumbers.is_valid_number(parsed)
            
            # Get number type
            number_type = phonenumbers.number_type(parsed)
            carrier_type = self._map_number_type(number_type)
            
            # Landlines more likely business
            is_business_line = carrier_type == "landline"
            
            # Low confidence for basic validation
            confidence = 0.5 if is_valid else 0.0
            
            return PhoneVerificationResult(
                phone=phone,
                is_valid=is_valid,
                carrier_type=carrier_type,
                is_business_line=is_business_line,
                confidence_score=confidence,
                provider_response={"method": "basic_validation"},
                verified_at=datetime.utcnow()
            )
        
        except Exception as e:
            logger.debug(f"Basic verification failed for {phone}: {e}")
            return self._invalid_result(phone)
    
    def _invalid_result(self, phone: str) -> PhoneVerificationResult:
        """
        Create invalid result.
        
        Args:
            phone: Phone number
            
        Returns:
            PhoneVerificationResult with is_valid=False
        """
        return PhoneVerificationResult(
            phone=phone,
            is_valid=False,
            carrier_type="unknown",
            is_business_line=False,
            confidence_score=0.0,
            provider_response={"error": "invalid_number"},
            verified_at=datetime.utcnow()
        )
    
    def _map_line_type(self, line_type: str) -> str:
        """
        Map provider line type to standard carrier type.
        
        Args:
            line_type: Provider-specific line type
            
        Returns:
            Standard carrier type
        """
        line_type = line_type.lower()
        
        if "landline" in line_type or "fixed" in line_type:
            return "landline"
        elif "mobile" in line_type or "cell" in line_type:
            return "mobile"
        elif "voip" in line_type:
            return "voip"
        else:
            return "unknown"
    
    def _map_number_type(self, number_type: int) -> str:
        """
        Map phonenumbers number type to carrier type.
        
        Args:
            number_type: phonenumbers.PhoneNumberType
            
        Returns:
            Carrier type string
        """
        if number_type == phonenumbers.PhoneNumberType.FIXED_LINE:
            return "landline"
        elif number_type == phonenumbers.PhoneNumberType.MOBILE:
            return "mobile"
        elif number_type == phonenumbers.PhoneNumberType.VOIP:
            return "voip"
        elif number_type == phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE:
            return "landline"  # Prefer landline for business
        else:
            return "unknown"
    
    def _calculate_confidence_twilio(self, data: Dict[str, Any], carrier_type: str) -> float:
        """
        Calculate confidence score from Twilio data.
        
        Args:
            data: Twilio response data
            carrier_type: Carrier type
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.7  # Base confidence for Twilio
        
        # Higher confidence for landline/VOIP (business)
        if carrier_type in ["landline", "voip"]:
            confidence += 0.2
        elif carrier_type == "mobile":
            confidence += 0.1
        
        # Check if carrier name is known
        carrier = data.get("carrier", {})
        if carrier.get("name"):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def meets_threshold(self, result: PhoneVerificationResult) -> bool:
        """
        Check if verification result meets confidence threshold.
        
        Args:
            result: Verification result
            
        Returns:
            True if meets threshold
        """
        threshold = self.settings.PHONE_VERIFICATION_CONFIDENCE_THRESHOLD
        return result.confidence_score >= threshold and result.is_valid
