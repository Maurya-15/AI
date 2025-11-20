"""Setup and run email campaign to 100 businesses."""

import subprocess
import sys

def main():
    """Setup and run the campaign."""
    print("=" * 70)
    print("DevSyncSalesAI - Email Campaign Setup")
    print("=" * 70)
    print()
    
    # Step 1: Add 100 business leads
    print("Step 1: Adding 100 business leads...")
    print("-" * 70)
    result = subprocess.run([sys.executable, "add_100_business_leads.py"], capture_output=False)
    if result.returncode != 0:
        print("❌ Failed to add leads")
        return
    
    print()
    print("=" * 70)
    print("✅ Setup Complete!")
    print("=" * 70)
    print()
    print("📧 Ready to send emails to 100 businesses")
    print("   - 99 real business emails")
    print("   - 1 demo email (anshum25506@gmail.com)")
    print()
    print("🚀 To send emails now:")
    print("   python trigger_campaign.py email")
    print()
    print("📅 Or wait for scheduled send at 10:00 AM IST daily")
    print()


if __name__ == "__main__":
    main()
