"""Script to add sample leads for testing."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.db import get_db_context, init_db
from app.models import Lead
from datetime import datetime

def add_sample_leads():
    """Add sample leads to database."""
    print("🔧 Initializing database...")
    init_db()
    
    print("📝 Adding sample leads...")
    
    sample_leads = [
        {
            "source": "google_maps",
            "business_name": "Tech Solutions Pvt Ltd",
            "city": "Bangalore",
            "category": "IT Services",
            "website": "https://techsolutions.example.com",
            "primary_email": "contact@techsolutions.example.com",
            "primary_phone": "+91-9876543210",
            "email_verified": True,
            "phone_verified": True,
            "verification_confidence": 0.95,
            "raw_metadata": {"rating": 4.5, "reviews": 120}
        },
        {
            "source": "justdial",
            "business_name": "Digital Marketing Agency",
            "city": "Mumbai",
            "category": "Marketing",
            "website": "https://digitalmarketing.example.com",
            "primary_email": "info@digitalmarketing.example.com",
            "primary_phone": "+91-9876543211",
            "email_verified": True,
            "phone_verified": True,
            "verification_confidence": 0.92,
            "raw_metadata": {"rating": 4.2, "reviews": 85}
        },
        {
            "source": "indiamart",
            "business_name": "Manufacturing Co",
            "city": "Delhi",
            "category": "Manufacturing",
            "website": "https://manufacturing.example.com",
            "primary_email": "sales@manufacturing.example.com",
            "primary_phone": "+91-9876543212",
            "email_verified": True,
            "phone_verified": True,
            "verification_confidence": 0.88,
            "raw_metadata": {"rating": 4.0, "reviews": 50}
        },
        {
            "source": "google_maps",
            "business_name": "Consulting Services Ltd",
            "city": "Pune",
            "category": "Consulting",
            "website": "https://consulting.example.com",
            "primary_email": "hello@consulting.example.com",
            "primary_phone": "+91-9876543213",
            "email_verified": True,
            "phone_verified": True,
            "verification_confidence": 0.90,
            "raw_metadata": {"rating": 4.7, "reviews": 200}
        },
        {
            "source": "linkedin_company",
            "business_name": "Software Development Inc",
            "city": "Hyderabad",
            "category": "Software",
            "website": "https://softwaredev.example.com",
            "primary_email": "contact@softwaredev.example.com",
            "primary_phone": "+91-9876543214",
            "email_verified": True,
            "phone_verified": True,
            "verification_confidence": 0.93,
            "raw_metadata": {"rating": 4.6, "reviews": 150}
        }
    ]
    
    with get_db_context() as db:
        # Check if leads already exist
        existing_count = db.query(Lead).count()
        
        if existing_count > 0:
            print(f"⚠️  Database already has {existing_count} leads")
            response = input("Do you want to add more sample leads? (y/n): ")
            if response.lower() != 'y':
                print("❌ Cancelled")
                return
        
        # Add leads
        added = 0
        for lead_data in sample_leads:
            # Check if lead already exists
            existing = db.query(Lead).filter(
                Lead.business_name == lead_data["business_name"]
            ).first()
            
            if existing:
                print(f"⏭️  Skipping '{lead_data['business_name']}' (already exists)")
                continue
            
            lead = Lead(**lead_data)
            db.add(lead)
            added += 1
            print(f"✅ Added: {lead_data['business_name']}")
        
        db.commit()
        
        # Show summary
        total_count = db.query(Lead).count()
        verified_count = db.query(Lead).filter(
            Lead.email_verified == True,
            Lead.phone_verified == True
        ).count()
        
        print("\n" + "=" * 60)
        print(f"✅ Successfully added {added} new leads")
        print(f"📊 Total leads in database: {total_count}")
        print(f"✓  Verified leads: {verified_count}")
        print("=" * 60)


if __name__ == "__main__":
    try:
        add_sample_leads()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
