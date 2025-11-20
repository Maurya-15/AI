"""JustDial HTML scraper with robots.txt respect."""

import httpx
from typing import List, Optional
from bs4 import BeautifulSoup
from robotexclusionrulesparser import RobotExclusionRulesParser
import logging
import asyncio

from app.scraper.base import BaseScraper, ScrapeQuery, RawLead, RateLimitError, SourceUnavailableError

logger = logging.getLogger(__name__)


class JustDialScraper(BaseScraper):
    """Scraper for JustDial business directory."""
    
    def __init__(self):
        """Initialize JustDial scraper."""
        super().__init__("justdial")
        self.base_url = "https://www.justdial.com"
        self.robots_parser = RobotExclusionRulesParser()
        self.user_agent = "DevSyncSalesAI/1.0 (Business Lead Scraper)"
        self.crawl_delay = 2.0  # Default crawl delay
    
    async def validate_source(self) -> bool:
        """
        Verify JustDial is accessible and check robots.txt.
        
        Returns:
            True if source is accessible
        """
        try:
            async with httpx.AsyncClient() as client:
                # Fetch robots.txt
                response = await client.get(
                    f"{self.base_url}/robots.txt",
                    headers={"User-Agent": self.user_agent},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    self.robots_parser.parse(response.text)
                    
                    # Check if we can access search pages
                    can_fetch = self.robots_parser.is_allowed(self.user_agent, "/search")
                    
                    # Get crawl delay if specified
                    delay = self.robots_parser.get_crawl_delay(self.user_agent)
                    if delay:
                        self.crawl_delay = float(delay)
                        logger.info(f"JustDial crawl delay set to {self.crawl_delay}s")
                    
                    return can_fetch
                
                return False
        except Exception as e:
            logger.error(f"Failed to validate JustDial: {e}")
            return False
    
    async def scrape(self, query: ScrapeQuery) -> List[RawLead]:
        """
        Scrape leads from JustDial.
        
        Args:
            query: Scrape query with location, category, max_results
            
        Returns:
            List of raw leads
        """
        logger.info(f"Scraping JustDial: {query.category} in {query.location}")
        
        # Check robots.txt before scraping
        search_path = f"/{query.location}/{query.category}"
        if not self.robots_parser.is_allowed(self.user_agent, search_path):
            logger.warning(f"JustDial robots.txt disallows scraping {search_path}")
            return []
        
        leads = []
        page = 1
        
        async with httpx.AsyncClient() as client:
            while len(leads) < query.max_results:
                # Build search URL
                search_url = f"{self.base_url}/{query.location}/{query.category}"
                if page > 1:
                    search_url += f"/page-{page}"
                
                # Respect crawl delay
                if page > 1:
                    await asyncio.sleep(self.crawl_delay)
                
                # Make request with retry
                async def make_request():
                    response = await client.get(
                        search_url,
                        headers={
                            "User-Agent": self.user_agent,
                            "Accept": "text/html,application/xhtml+xml",
                            "Accept-Language": "en-US,en;q=0.9"
                        },
                        timeout=30.0,
                        follow_redirects=True
                    )
                    
                    if response.status_code == 429:
                        raise RateLimitError("JustDial rate limit exceeded")
                    elif response.status_code >= 500:
                        raise SourceUnavailableError(f"JustDial error: {response.status_code}")
                    
                    response.raise_for_status()
                    return response.text
                
                try:
                    html = await self.retry_with_backoff(make_request)
                except Exception as e:
                    logger.error(f"Failed to scrape JustDial page {page}: {e}")
                    break
                
                # Parse HTML
                page_leads = self._parse_search_results(html, query.location, query.category)
                
                if not page_leads:
                    # No more results
                    break
                
                leads.extend(page_leads)
                
                if len(leads) >= query.max_results:
                    leads = leads[:query.max_results]
                    break
                
                page += 1
                
                # Limit to reasonable number of pages
                if page > 10:
                    break
        
        # Deduplicate
        unique_leads = self.deduplicate_leads(leads)
        
        logger.info(f"Scraped {len(unique_leads)} unique leads from JustDial")
        return unique_leads
    
    def _parse_search_results(self, html: str, location: str, category: str) -> List[RawLead]:
        """
        Parse search results HTML.
        
        Args:
            html: HTML content
            location: Search location
            category: Search category
            
        Returns:
            List of raw leads
        """
        leads = []
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Find business listings (JustDial structure may vary)
            # This is a simplified parser - actual implementation would need
            # to handle JustDial's specific HTML structure
            
            listings = soup.find_all('li', class_='cntanr')
            
            for listing in listings:
                try:
                    lead = self._parse_listing(listing, location, category)
                    if lead:
                        leads.append(lead)
                except Exception as e:
                    logger.debug(f"Failed to parse listing: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Failed to parse JustDial HTML: {e}")
        
        return leads
    
    def _parse_listing(self, listing, location: str, category: str) -> Optional[RawLead]:
        """
        Parse individual business listing.
        
        Args:
            listing: BeautifulSoup element
            location: Location
            category: Category
            
        Returns:
            RawLead or None
        """
        try:
            # Extract business name
            name_elem = listing.find('span', class_='jcn')
            if not name_elem:
                return None
            business_name = name_elem.get_text(strip=True)
            
            # Extract phone numbers
            phone_numbers = []
            phone_elems = listing.find_all('p', class_='contact-info')
            for elem in phone_elems:
                phone_text = elem.get_text(strip=True)
                # Extract numbers from text
                import re
                numbers = re.findall(r'[\d\s\-\+\(\)]+', phone_text)
                for num in numbers:
                    normalized = self.normalize_phone(num)
                    if normalized and normalized not in phone_numbers:
                        phone_numbers.append(normalized)
            
            # Extract website
            website = None
            website_elem = listing.find('a', class_='website')
            if website_elem and website_elem.get('href'):
                website = website_elem['href']
            
            # Extract emails (if available)
            emails = []
            email_elem = listing.find('a', href=lambda x: x and 'mailto:' in x)
            if email_elem:
                email = email_elem['href'].replace('mailto:', '')
                if self.validate_email(email):
                    emails.append(email)
            
            # Extract address for city verification
            address_elem = listing.find('span', class_='mrehover')
            address = address_elem.get_text(strip=True) if address_elem else ""
            
            return RawLead(
                source=self.source_name,
                business_name=self.clean_business_name(business_name),
                city=location,
                category=category,
                website=website,
                phone_numbers=phone_numbers,
                emails=emails,
                raw_metadata={
                    "address": address,
                    "source_url": f"{self.base_url}/{location}/{category}"
                }
            )
        
        except Exception as e:
            logger.debug(f"Failed to parse listing: {e}")
            return None
