"""Add demo contact for testing."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.db import get_db_context, init_db
from app.models import Lead

def add_demo_contact():
    """Add demo contact."""
    print("🔧 Initializing database...")
    init_db()
    
    print("📝 Adding demo contact...")
    
    demo_contact = {
        "source": "google_maps",
        "business_name": "Demo Test Company",
        "city": "Test City",
        "category": "Technology",
        "website": "https://demo.example.com",
        "primary_email": "anshum25506@gmail.com",
        "primary_phone": "+917698895249",
        "email_verified": True,
        "phone_verified": True,
        "verification_confidence": 1.0,
        "raw_metadata": {"demo": True}
    }
    
    with get_db_context() as db:
        # Check if contact already exists
        existing = db.query(Lead).filter(
            Lead.primary_email == demo_contact["primary_email"]
        ).first()
        
        if existing:
            print(f"⚠️  Demo contact already exists (ID: {existing.id})")
            print(f"   Email: {existing.primary_email}")
            print(f"   Phone: {existing.primary_phone}")
            return existing.id
        
        # Add contact
        lead = Lead(**demo_contact)
        db.add(lead)
        db.commit()
        
        print(f"✅ Added demo contact (ID: {lead.id})")
        print(f"   Email: {lead.primary_email}")
        print(f"   Phone: {lead.primary_phone}")
        
        return lead.id


if __name__ == "__main__":
    try:
        lead_id = add_demo_contact()
        
        print("\n" + "=" * 60)
        print("⚠️  IMPORTANT: System is in DRY-RUN mode")
        print("=" * 60)
        print("To actually send emails/calls:")
        print("1. Edit .env file and set: DRY_RUN_MODE=false")
        print("2. Ensure SendGrid API key is valid")
        print("3. Ensure Twilio credentials are valid")
        print("4. Restart the application")
        print("5. Run: python trigger_campaign.py email")
        print("   or: python trigger_campaign.py call")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
