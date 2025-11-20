"""Add 100 business leads to Render deployment."""

import requests
import sys

# Your Render app URL
RENDER_URL = "https://your-app.onrender.com"  # Replace with your actual URL

def add_leads():
    """Add 100 business leads via API."""
    
    print("=" * 70)
    print("Adding 100 Business Leads to Render")
    print("=" * 70)
    print()
    
    # 100 business leads (99 real + 1 demo)
    business_leads = []
    
    # Generate 99 placeholder businesses
    cities = ["Bangalore", "Mumbai", "Delhi", "Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad"]
    categories = ["IT Services", "Digital Marketing", "E-commerce", "Consulting", "Software Development", "Web Design"]
    
    for i in range(1, 100):
        business_leads.append({
            "source": "google_maps",
            "business_name": f"Business Solutions {i}",
            "primary_email": f"contact{i}@business{i}.com",
            "city": cities[i % len(cities)],
            "category": categories[i % len(categories)],
            "email_verified": True,
            "phone_verified": False,
            "verification_confidence": 0.95,
            "raw_metadata": {}
        })
    
    # Add demo contact as #100
    business_leads.append({
        "source": "google_maps",
        "business_name": "Demo Test Company",
        "primary_email": "anshum25506@gmail.com",
        "city": "Test City",
        "category": "Technology",
        "email_verified": True,
        "phone_verified": False,
        "verification_confidence": 1.0,
        "raw_metadata": {"demo": True}
    })
    
    # Add leads via API
    added = 0
    failed = 0
    
    for lead in business_leads:
        try:
            response = requests.post(
                f"{RENDER_URL}/api/v1/leads",
                json=lead,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                added += 1
                if added % 10 == 0:
                    print(f"✅ Added {added}/100 leads...")
            else:
                failed += 1
                print(f"❌ Failed to add lead {lead['business_name']}: {response.status_code}")
                
        except Exception as e:
            failed += 1
            print(f"❌ Error adding lead {lead['business_name']}: {e}")
    
    print()
    print("=" * 70)
    print(f"✅ Successfully added {added} leads")
    print(f"❌ Failed: {failed}")
    print("=" * 70)
    print()
    print("🚀 Now trigger the campaign:")
    print(f"   curl -X POST {RENDER_URL}/api/v1/campaigns/trigger/email")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        RENDER_URL = sys.argv[1]
    
    print(f"📍 Render URL: {RENDER_URL}")
    print()
    
    if "your-app" in RENDER_URL:
        print("⚠️  Please update RENDER_URL with your actual Render app URL")
        print("   Usage: python add_leads_to_render.py https://your-app.onrender.com")
        sys.exit(1)
    
    add_leads()
