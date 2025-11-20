"""Email personalization using AI."""

import httpx
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import asyncio

from app.config import get_settings
from app.models import Lead

logger = logging.getLogger(__name__)


@dataclass
class PersonalizedEmail:
    """Personalized email content."""
    subject: str
    body_html: str
    body_text: str
    personalization_method: str  # 'ai' or 'template'
    generated_at: datetime


class EmailPersonalizer:
    """AI-powered email personalization service."""
    
    def __init__(self):
        """Initialize personalizer."""
        self.settings = get_settings()
        self.timeout = 5.0  # 5-second timeout for AI calls
    
    async def generate(self, lead: Lead) -> PersonalizedEmail:
        """
        Generate personalized email content for lead.
        
        Args:
            lead: Lead to personalize for
            
        Returns:
            PersonalizedEmail
        """
        try:
            return await self.generate_with_fallback(lead)
        except Exception as e:
            logger.error(f"Failed to generate email for lead {lead.id}: {e}")
            return self._fallback_template(lead)
    
    async def generate_with_fallback(self, lead: Lead) -> PersonalizedEmail:
        """
        Generate with template fallback on AI failure.
        
        Args:
            lead: Lead to personalize for
            
        Returns:
            PersonalizedEmail
        """
        # Try AI generation first
        if self.settings.OPENAI_API_KEY:
            try:
                return await asyncio.wait_for(
                    self._generate_with_openai(lead),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"OpenAI timeout for lead {lead.id}, using template")
            except Exception as e:
                logger.warning(f"OpenAI failed for lead {lead.id}: {e}, using template")
        
        elif self.settings.AIMLAPI_KEY:
            try:
                return await asyncio.wait_for(
                    self._generate_with_aimlapi(lead),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"AIMLAPI timeout for lead {lead.id}, using template")
            except Exception as e:
                logger.warning(f"AIMLAPI failed for lead {lead.id}: {e}, using template")
        
        # Fallback to template
        return self._fallback_template(lead)
    
    async def _generate_with_openai(self, lead: Lead) -> PersonalizedEmail:
        """
        Generate email using OpenAI GPT-4.
        
        Args:
            lead: Lead to personalize for
            
        Returns:
            PersonalizedEmail
        """
        prompt = self._build_prompt(lead)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": "You are a professional business email writer."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 200,
                    "temperature": 0.7
                },
                timeout=self.timeout
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract generated content
            content = data["choices"][0]["message"]["content"].strip()
            
            # Validate content
            if not self._validate_content(content, lead):
                logger.warning(f"AI content validation failed for lead {lead.id}")
                return self._fallback_template(lead)
            
            # Parse into subject and body
            subject, body = self._parse_ai_content(content, lead)
            
            return PersonalizedEmail(
                subject=subject,
                body_html=self._format_html(body),
                body_text=body,
                personalization_method="ai",
                generated_at=datetime.utcnow()
            )
    
    async def _generate_with_aimlapi(self, lead: Lead) -> PersonalizedEmail:
        """
        Generate email using AIMLAPI.
        
        Args:
            lead: Lead to personalize for
            
        Returns:
            PersonalizedEmail
        """
        # Similar implementation to OpenAI
        # This is a placeholder - actual AIMLAPI endpoint may differ
        prompt = self._build_prompt(lead)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.aimlapi.com/v1/generate",  # Placeholder URL
                headers={
                    "Authorization": f"Bearer {self.settings.AIMLAPI_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "prompt": prompt,
                    "max_tokens": 200
                },
                timeout=self.timeout
            )
            
            response.raise_for_status()
            data = response.json()
            
            content = data.get("text", "").strip()
            
            if not self._validate_content(content, lead):
                return self._fallback_template(lead)
            
            subject, body = self._parse_ai_content(content, lead)
            
            return PersonalizedEmail(
                subject=subject,
                body_html=self._format_html(body),
                body_text=body,
                personalization_method="ai",
                generated_at=datetime.utcnow()
            )
    
    def _build_prompt(self, lead: Lead) -> str:
        """
        Build AI prompt for email generation.
        
        Args:
            lead: Lead information
            
        Returns:
            Prompt string
        """
        return f"""Write a brief, professional cold email for DevSync Innovation, a web development company in India.

Business Details:
- Name: {lead.business_name}
- Category: {lead.category}
- City: {lead.city}

Write a 3-line email:
Line 1: Personalized hook referencing their business or industry
Line 2: Value proposition - "We build fast, SEO-ready websites for {lead.category} businesses"
Line 3: Clear CTA with scheduling link

Keep it under 80 words. Be professional but friendly. No pushy sales language.
Format: Start with subject line, then body."""
    
    def _fallback_template(self, lead: Lead) -> PersonalizedEmail:
        """
        Generate email using fallback template.
        
        Args:
            lead: Lead information
            
        Returns:
            PersonalizedEmail
        """
        subject = f"Website Solutions for {lead.business_name}"
        
        body = f"""Hi {lead.business_name} team,

I noticed you're in the {lead.category} space in {lead.city}, and I wanted to share something quick —
most businesses in your category are losing 30–50% of potential customers due to slow or outdated websites.

At DevSync Innovation, we build fast, SEO-optimized websites that bring in more leads and help your business stand out locally.

Would you like to be connect with us and quick 10–15 minute call this week to see if we can help you increase your online visibility?

You can also check our work here: https://www.devsyncinnovation.in and book slot

Best regards,
DevSync Innovation Team"""
        
        return PersonalizedEmail(
            subject=subject,
            body_html=self._format_html(body),
            body_text=body,
            personalization_method="template",
            generated_at=datetime.utcnow()
        )
    
    def _validate_content(self, content: str, lead: Lead) -> bool:
        """
        Validate AI-generated content.
        
        Args:
            content: Generated content
            lead: Lead information
            
        Returns:
            True if content is valid
        """
        # Check length (50-150 words)
        word_count = len(content.split())
        if word_count < 50 or word_count > 150:
            return False
        
        # Check for required elements
        content_lower = content.lower()
        
        # Should mention DevSync Innovation
        if "devsync" not in content_lower:
            return False
        
        # Should have some personalization (business name or category)
        if lead.business_name.lower() not in content_lower and lead.category.lower() not in content_lower:
            return False
        
        return True
    
    def _parse_ai_content(self, content: str, lead: Lead) -> tuple[str, str]:
        """
        Parse AI content into subject and body.
        
        Args:
            content: AI-generated content
            lead: Lead information
            
        Returns:
            Tuple of (subject, body)
        """
        lines = content.strip().split('\n')
        
        # Try to find subject line
        subject = None
        body_start = 0
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if line_lower.startswith('subject:'):
                subject = line.split(':', 1)[1].strip()
                body_start = i + 1
                break
        
        # If no subject found, use default
        if not subject:
            subject = f"Website Solutions for {lead.business_name}"
            body_start = 0
        
        # Get body
        body = '\n'.join(lines[body_start:]).strip()
        
        return subject, body
    
    def _format_html(self, text: str) -> str:
        """
        Format plain text as HTML.
        
        Args:
            text: Plain text
            
        Returns:
            HTML string
        """
        # Simple HTML formatting
        paragraphs = text.split('\n\n')
        html_paragraphs = [f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip()]
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        p {{ margin: 10px 0; }}
    </style>
</head>
<body>
    {''.join(html_paragraphs)}
</body>
</html>"""
