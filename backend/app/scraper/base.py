"""Base scraper class and utilities."""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
import logging
import asyncio
import random

logger = logging.getLogger(__name__)


@dataclass
class ScrapeQuery:
    """Scrape query parameters."""
    location: str
    category: str
    max_results: int = 50


@dataclass
class RawLead:
    """Raw lead data from scraper."""
    source: str
    business_name: str
    city: str
    category: str
    website: Optional[str]
    phone_numbers: List[str]
    emails: List[str]
    raw_metadata: dict


class BaseScraper(ABC):
    """Abstract base class for scrapers."""
    
    def __init__(self):
        """Initialize scraper."""
        self.source_name = "unknown"
    
    @abstractmethod
    async def scrape(self, query: ScrapeQuery) -> List[RawLead]:
        """Scrape leads based on query."""
        pass
    
    @abstractmethod
    async def validate_source(self) -> bool:
        """Verify scraper can access the source."""
        pass
    
    async def scrape_with_backoff(self, query: ScrapeQuery, max_retries: int = 3) -> List[RawLead]:
        """Scrape with exponential backoff on rate limits."""
        for attempt in range(max_retries):
            try:
                return await self.scrape(query)
            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    if attempt < max_retries - 1:
                        delay = self._calculate_backoff(attempt)
                        logger.warning(f"Rate limited, retrying in {delay}s")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Exhausted retries for {self.source_name}")
                        raise
                else:
                    raise
        return []
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with jitter."""
        base_delay = 1.0
        max_delay = 60.0
        delay = min(base_delay * (2 ** attempt), max_delay)
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter
    
    def normalize_phone(self, phone: str, country_code: str = "+91") -> str:
        """Normalize phone to E.164 format."""
        # Remove non-digits
        digits = ''.join(c for c in phone if c.isdigit())
        
        # Add country code if missing
        if not digits.startswith(country_code.replace('+', '')):
            digits = country_code.replace('+', '') + digits
        
        return '+' + digits
    
    def deduplicate_leads(self, leads: List[RawLead]) -> List[RawLead]:
        """Deduplicate based on (business_name, website, phone)."""
        seen = set()
        unique_leads = []
        
        for lead in leads:
            key = (
                lead.business_name.lower().strip(),
                lead.website.lower().strip() if lead.website else "",
                lead.phone_numbers[0] if lead.phone_numbers else ""
            )
            
            if key not in seen:
                seen.add(key)
                unique_leads.append(lead)
        
        return unique_leads
