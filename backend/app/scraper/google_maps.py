"""Google Maps Places API scraper."""

import httpx
from typing import List, Optional
import logging

from app.scraper.base import BaseScraper, ScrapeQuery, RawLead, RateLimitError, SourceUnavailableError
from app.config import get_settings

logger = logging.getLogger(__name__)


class GoogleMapsScraper(BaseScraper):
    """Scraper for Google Maps Places API."""
    
    def __init__(self):
        """Initialize Google Maps scraper."""
        super().__init__("google_maps")
        self.settings = get_settings()
        self.api_key = self.settings.GOOGLE_MAPS_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/place"
    
    async def validate_source(self) -> bool:
        """
        Verify Google Maps API is accessible.
        
        Returns:
            True if API key is valid and service is accessible
        """
        if not self.api_key:
            logger.error("Google Maps API key not configured")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                # Test with a simple query
                response = await client.get(
                    f"{self.base_url}/textsearch/json",
                    params={
                        "query": "restaurant",
                        "key": self.api_key
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") in ["OK", "ZERO_RESULTS"]:
                        return True
                    elif data.get("status") == "REQUEST_DENIED":
                        logger.error(f"Google Maps API access denied: {data.get('error_message')}")
                        return False
                
                return False
        except Exception as e:
            logger.error(f"Failed to validate Google Maps API: {e}")
            return False
    
    async def scrape(self, query: ScrapeQuery) -> List[RawLead]:
        """
        Scrape leads from Google Maps Places API.
        
        Args:
            query: Scrape query with location, category, max_results
            
        Returns:
            List of raw leads
        """
        if not self.api_key:
            raise ValueError("Google Maps API key not configured")
        
        logger.info(f"Scraping Google Maps: {query.category} in {query.location}")
        
        # Build search query
        search_query = f"{query.category} in {query.location}"
        
        leads = []
        next_page_token = None
        
        async with httpx.AsyncClient() as client:
            while len(leads) < query.max_results:
                # Prepare request
                params = {
                    "query": search_query,
                    "key": self.api_key
                }
                
                if next_page_token:
                    params["pagetoken"] = next_page_token
                
                # Make request with retry
                async def make_request():
                    response = await client.get(
                        f"{self.base_url}/textsearch/json",
                        params=params,
                        timeout=30.0
                    )
                    
                    if response.status_code == 429:
                        raise RateLimitError("Google Maps API rate limit exceeded")
                    elif response.status_code >= 500:
                        raise SourceUnavailableError(f"Google Maps API error: {response.status_code}")
                    
                    response.raise_for_status()
                    return response.json()
                
                try:
                    data = await self.retry_with_backoff(make_request)
                except Exception as e:
                    logger.error(f"Failed to scrape Google Maps: {e}")
                    break
                
                # Check status
                if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                    logger.error(f"Google Maps API error: {data.get('status')} - {data.get('error_message')}")
                    break
                
                # Parse results
                results = data.get("results", [])
                if not results:
                    break
                
                for place in results:
                    lead = await self._parse_place(place, client)
                    if lead:
                        leads.append(lead)
                    
                    if len(leads) >= query.max_results:
                        break
                
                # Check for next page
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break
                
                # Google requires a short delay before using next_page_token
                import asyncio
                await asyncio.sleep(2)
        
        # Deduplicate
        unique_leads = self.deduplicate_leads(leads)
        
        logger.info(f"Scraped {len(unique_leads)} unique leads from Google Maps")
        return unique_leads
    
    async def _parse_place(self, place: dict, client: httpx.AsyncClient) -> Optional[RawLead]:
        """
        Parse place data into RawLead.
        
        Args:
            place: Place data from API
            client: HTTP client for additional requests
            
        Returns:
            RawLead or None if parsing fails
        """
        try:
            business_name = place.get("name")
            if not business_name:
                return None
            
            # Get place details for more information
            place_id = place.get("place_id")
            details = await self._get_place_details(place_id, client) if place_id else {}
            
            # Extract contact information
            phone_numbers = []
            if details.get("formatted_phone_number"):
                normalized = self.normalize_phone(details["formatted_phone_number"])
                if normalized:
                    phone_numbers.append(normalized)
            
            emails = []
            # Google Maps doesn't provide emails directly
            
            # Extract website
            website = details.get("website")
            
            # Extract address components
            city = None
            address_components = place.get("address_components", [])
            for component in address_components:
                if "locality" in component.get("types", []):
                    city = component.get("long_name")
                    break
            
            # If no city from address, try formatted_address
            if not city:
                formatted_address = place.get("formatted_address", "")
                # Simple extraction - take second-to-last part
                parts = formatted_address.split(",")
                if len(parts) >= 2:
                    city = parts[-2].strip()
            
            # Extract category
            category = place.get("types", ["business"])[0] if place.get("types") else "business"
            
            return RawLead(
                source=self.source_name,
                business_name=self.clean_business_name(business_name),
                city=city or "Unknown",
                category=category,
                website=website,
                phone_numbers=phone_numbers,
                emails=emails,
                raw_metadata={
                    "place_id": place_id,
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("user_ratings_total"),
                    "formatted_address": place.get("formatted_address"),
                    "types": place.get("types", [])
                }
            )
        except Exception as e:
            logger.error(f"Failed to parse place: {e}")
            return None
    
    async def _get_place_details(self, place_id: str, client: httpx.AsyncClient) -> dict:
        """
        Get detailed information about a place.
        
        Args:
            place_id: Google Place ID
            client: HTTP client
            
        Returns:
            Place details dictionary
        """
        try:
            response = await client.get(
                f"{self.base_url}/details/json",
                params={
                    "place_id": place_id,
                    "fields": "formatted_phone_number,website,address_components",
                    "key": self.api_key
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "OK":
                    return data.get("result", {})
            
            return {}
        except Exception as e:
            logger.debug(f"Failed to get place details: {e}")
            return {}
