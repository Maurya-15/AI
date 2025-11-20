"""Direct test to make call to demo contact."""

import sys
import os
import asyncio
from datetime import datetime
import pytz

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.db import get_db_context, init_db
from app.models import Lead
from app.outreach.caller import get_voice_caller
from app.config import get_settings

async def send_test_call():
    """Make test call to demo contact."""
    print("🔧 Initializing...")
    init_db()
    
    # Check configuration
    settings = get_settings()
    print(f"DRY_RUN_MODE: {settings.DRY_RUN_MODE}")
    print()
    
    # Check Vonage
    print("Vonage Configuration:")
    print(f"  API Key: {'✅ Configured' if settings.VONAGE_API_KEY else '❌ Missing'}")
    print(f"  API Secret: {'✅ Configured' if settings.VONAGE_API_SECRET else '❌ Missing'}")
    print(f"  Phone: {settings.VONAGE_PHONE_NUMBER if settings.VONAGE_PHONE_NUMBER else '❌ Missing'}")
    print()
    
    # Check Twilio
    print("Twilio Configuration:")
    print(f"  Account SID: {'✅ Configured' if settings.TWILIO_ACCOUNT_SID else '❌ Missing'}")
    print(f"  Auth Token: {'✅ Configured' if settings.TWILIO_AUTH_TOKEN else '❌ Missing'}")
    print(f"  Phone: {settings.TWILIO_PHONE_NUMBER if settings.TWILIO_PHONE_NUMBER else '❌ Missing'}")
    print()
    
    # Check call window
    caller = get_voice_caller()
    print(f"Using Provider: {caller.provider.upper()}")
    print()
    
    ist = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(ist)
    
    print(f"Current Time: {now.strftime('%I:%M %p %Z')} ({now.strftime('%A')})")
    print(f"Call Window: {settings.CALL_WINDOW_START} - {settings.CALL_WINDOW_END} IST (Monday-Friday)")
    
    if caller.is_in_call_window(now):
        print("✅ Within call window")
    else:
        print("❌ Outside call window")
        print("   Calls can only be made 11 AM - 5 PM IST, Monday-Friday")
        if not settings.DRY_RUN_MODE:
            print("   Set DRY_RUN_MODE=true in .env to test outside call window")
            return
    print()
    
    # Get demo contact and keep in session
    with get_db_context() as db:
        lead = db.query(Lead).filter(Lead.primary_phone == "+917698895249").first()
        
        if not lead:
            print("❌ Demo contact not found!")
            print("Run: python add_demo_contact.py")
            return
        
        print(f"📞 Calling: {lead.primary_phone}")
        print(f"Business: {lead.business_name}")
        print()
        
        try:
            # Initiate call while lead is still in session
            print("📤 Initiating call...")
            result = await caller.initiate_call(lead)
        
            if result.status in ["initiated", "completed"]:
                print(f"✅ Call initiated successfully!")
                print(f"Call SID: {result.call_sid}")
                if result.status == "completed":
                    print(f"Status: {result.status}")
                    if result.outcome:
                        print(f"Outcome: {result.outcome}")
                print(f"\n🎉 Call should be ringing at: {lead.primary_phone}")
            else:
                print(f"❌ Failed to initiate call")
                print(f"Status: {result.status}")
                if result.error:
                    print(f"Error: {result.error}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(send_test_call())
