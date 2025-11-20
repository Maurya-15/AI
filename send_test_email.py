"""Direct test to send email to demo contact."""

import sys
import os
import asyncio

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.db import get_db_context, init_db
from app.models import Lead
from app.outreach.personalizer import EmailPersonalizer
from app.outreach.emailer import EmailSender, OutreachEmail
from app.config import get_settings

async def send_test_email():
    """Send test email to demo contact."""
    print("🔧 Initializing...")
    init_db()
    
    # Check configuration
    settings = get_settings()
    print(f"DRY_RUN_MODE: {settings.DRY_RUN_MODE}")
    print(f"APPROVAL_MODE: {settings.APPROVAL_MODE}")
    print(f"SendGrid API Key: {'✅ Configured' if settings.SENDGRID_API_KEY else '❌ Missing'}")
    print()
    
    # Get demo contact and extract data
    with get_db_context() as db:
        lead_obj = db.query(Lead).filter(Lead.primary_email == "anshum25506@gmail.com").first()
        
        if not lead_obj:
            print("❌ Demo contact not found!")
            print("Run: python add_demo_contact.py")
            return
        
        # Extract all needed data while in session
        lead_data = {
            'id': lead_obj.id,
            'business_name': lead_obj.business_name,
            'primary_email': lead_obj.primary_email,
            'city': lead_obj.city,
            'category': lead_obj.category,
            'website': lead_obj.website
        }
        
        print(f"📧 Sending email to: {lead_data['primary_email']}")
        print(f"Business: {lead_data['business_name']}")
        print()
    
    try:
        # Create a simple Lead-like object for personalization
        class LeadData:
            def __init__(self, data):
                for key, value in data.items():
                    setattr(self, key, value)
        
        lead = LeadData(lead_data)
        
        # Generate personalized content
        print("✍️  Generating personalized content...")
        personalizer = EmailPersonalizer()
        personalized = await personalizer.generate(lead)
        
        print(f"Subject: {personalized.subject}")
        print(f"Method: {personalized.personalization_method}")
        print()
        
        # Create email
        emailer = EmailSender()
        outreach_email = OutreachEmail(
            lead_id=lead.id,
            to_email=lead.primary_email,
            subject=personalized.subject,
            body_html=personalized.body_html,
            body_text=personalized.body_text,
            unsubscribe_token=emailer.generate_unsubscribe_token()
        )
        
        # Send email
        print("📤 Sending email...")
        result = await emailer.send(outreach_email)
        
        if result.success:
            print(f"✅ Email sent successfully!")
            print(f"Message ID: {result.message_id}")
            print(f"\n🎉 Check inbox: {lead.primary_email}")
        else:
            print(f"❌ Failed to send email")
            print(f"Error: {result.error}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(send_test_email())
