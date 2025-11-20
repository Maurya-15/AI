"""Seed database with test leads."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db import get_db_context, init_db
from app.models import Lead
from datetime import datetime

def seed_leads():
    """Seed database with test leads."""
    
    # Initialize database
    init_db()
    
    test_leads = [
        {
            "source": "google_maps",
            "business_name": "Mumbai Restaurant",
            "city": "Mumbai",
            "category": "restaurant",
            "website": "https://mumbairestaurant.example.com",
            "primary_email": "info@mumbairestaurant.example.com",
            "primary_phone": "+919876543210",
            "email_verified": True,
            "phone_verified": True
        },
        {
            "source": "justdial",
            "business_name": "Delhi Retail Store",
            "city": "Delhi",
            "category": "retail",
            "website": "https://delhiretail.example.com",
            "primary_email": "contact@delhiretail.example.com",
            "primary_phone": "+919876543211",
            "email_verified": True,
            "phone_verified": True
        },
        {
            "source": "google_maps",
            "business_name": "Bangalore Tech Services",
            "city": "Bangalore",
            "category": "services",
            "website": "https://bangaloretech.example.com",
            "primary_email": "hello@bangaloretech.example.com",
            "primary_phone": "+919876543212",
            "email_verified": True,
            "phone_verified": True
        },
        {
            "source": "indiamart",
            "business_name": "Chennai Manufacturing",
            "city": "Chennai",
            "category": "manufacturing",
            "website": "https://chennaimfg.example.com",
            "primary_email": "sales@chennaimfg.example.com",
            "primary_phone": "+919876543213",
            "email_verified": True,
            "phone_verified": True
        },
        {
            "source": "google_maps",
            "business_name": "Kolkata Consulting",
            "city": "Kolkata",
            "category": "services",
            "website": "https://kolkataconsult.example.com",
            "primary_email": "info@kolkataconsult.example.com",
            "primary_phone": "+919876543214",
            "email_verified": True,
            "phone_verified": True
        }
    ]
    
    with get_db_context() as db:
        for lead_data in test_leads:
            # Check if lead already exists
            existing = db.query(Lead).filter(
                Lead.business_name == lead_data["business_name"]
            ).first()
            
            if not existing:
                lead = Lead(**lead_data)
                db.add(lead)
                print(f"Added: {lead_data['business_name']}")
            else:
                print(f"Skipped (exists): {lead_data['business_name']}")
        
        db.commit()
    
    print(f"\nSeeding complete! Added {len(test_leads)} test leads.")

if __name__ == "__main__":
    seed_leads()
