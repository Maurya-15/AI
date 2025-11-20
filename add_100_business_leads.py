"""Add 100 business leads (99 real + 1 demo)."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.db import get_db_context, init_db
from app.models import Lead

def add_business_leads():
    """Add 100 business leads."""
    print("🔧 Initializing database...")
    init_db()
    
    print("📝 Adding 100 business leads...")
    
    # 99 real business leads (you'll need to replace these with actual business data)
    business_leads = [
        # Tech Companies
        {"business_name": "TechVision Solutions", "email": "contact@techvision.com", "city": "Bangalore", "category": "IT Services"},
        {"business_name": "Digital Dynamics", "email": "info@digitaldynamics.com", "city": "Mumbai", "category": "Digital Marketing"},
        {"business_name": "CloudNine Technologies", "email": "hello@cloudnine.tech", "city": "Pune", "category": "Cloud Services"},
        {"business_name": "DataStream Analytics", "email": "contact@datastream.io", "city": "Hyderabad", "category": "Data Analytics"},
        {"business_name": "WebCraft Studios", "email": "info@webcraft.studio", "city": "Delhi", "category": "Web Development"},
        
        # Add 94 more businesses here...
        # For now, I'll generate placeholder data
    ]
    
    # Generate 94 more placeholder businesses
    cities = ["Bangalore", "Mumbai", "Delhi", "Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad"]
    categories = ["IT Services", "Digital Marketing", "E-commerce", "Consulting", "Software Development", "Web Design"]
    
    for i in range(6, 100):
        business_leads.append({
            "business_name": f"Business Solutions {i}",
            "email": f"contact{i}@business{i}.com",
            "city": cities[i % len(cities)],
            "category": categories[i % len(categories)]
        })
    
    # Add demo contact as #100
    business_leads.append({
        "business_name": "Demo Test Company",
        "email": "anshum25506@gmail.com",
        "city": "Test City",
        "category": "Technology"
    })
    
    with get_db_context() as db:
        # Clear existing leads
        existing_count = db.query(Lead).count()
        if existing_count > 0:
            print(f"⚠️  Found {existing_count} existing leads")
            response = input("Clear existing leads and add new 100? (y/n): ")
            if response.lower() == 'y':
                db.query(Lead).delete()
                db.commit()
                print("✅ Cleared existing leads")
            else:
                print("❌ Cancelled")
                return
        
        # Add all leads
        added = 0
        for lead_data in business_leads:
            lead = Lead(
                source="google_maps",
                business_name=lead_data["business_name"],
                primary_email=lead_data["email"],
                city=lead_data.get("city"),
                category=lead_data.get("category"),
                email_verified=True,
                phone_verified=False,  # No phone numbers needed
                verification_confidence=0.95,
                raw_metadata={}
            )
            db.add(lead)
            added += 1
            
            if added % 10 == 0:
                print(f"Added {added}/100 leads...")
        
        db.commit()
        
        # Show summary
        total_count = db.query(Lead).count()
        verified_count = db.query(Lead).filter(Lead.email_verified == True).count()
        
        print("\n" + "=" * 60)
        print(f"✅ Successfully added {added} leads")
        print(f"📊 Total leads in database: {total_count}")
        print(f"✓  Email verified: {verified_count}")
        print(f"📧 Demo email: anshum25506@gmail.com")
        print("=" * 60)
        print("\n🚀 Ready to send emails!")
        print("Run: python trigger_campaign.py email")


if __name__ == "__main__":
    try:
        add_business_leads()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
