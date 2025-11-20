"""Send emails immediately to all eligible businesses."""

import sys
import os
import asyncio

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.scheduler import get_scheduler
from app.db import init_db
from app.config import get_settings

async def send_emails_now():
    """Send emails immediately."""
    print("=" * 70)
    print("📧 DevSyncSalesAI - Send Emails NOW")
    print("=" * 70)
    print()
    
    # Initialize
    print("🔧 Initializing...")
    init_db()
    
    settings = get_settings()
    print(f"📤 Email From: {settings.EMAIL_FROM}")
    print(f"📧 Daily Cap: {settings.DAILY_EMAIL_CAP}")
    print(f"🔒 DRY_RUN_MODE: {settings.DRY_RUN_MODE}")
    print()
    
    # Get scheduler and execute campaign
    print("🚀 Starting email campaign...")
    print("-" * 70)
    
    scheduler = get_scheduler()
    report = await scheduler.execute_email_campaign()
    
    if report:
        print()
        print("=" * 70)
        print("✅ Email Campaign Completed!")
        print("=" * 70)
        print(f"📊 Campaign ID: {report.campaign_id}")
        print(f"📤 Total Attempted: {report.total_attempted}")
        print(f"✅ Total Success: {report.total_success}")
        print(f"❌ Total Failed: {report.total_failed}")
        print(f"⏱️  Duration: {(report.completed_at - report.started_at).total_seconds():.2f} seconds")
        
        if report.errors:
            print(f"\n⚠️  Errors ({len(report.errors)}):")
            for error in report.errors[:5]:
                print(f"   - {error}")
        
        print("=" * 70)
        print()
        
        if report.total_success > 0:
            print(f"🎉 Successfully sent {report.total_success} emails!")
            print(f"📬 Check inbox: anshum25506@gmail.com")
        
    else:
        print()
        print("❌ Campaign failed to execute")
        print("   Check logs for details")


if __name__ == "__main__":
    try:
        asyncio.run(send_emails_now())
    except KeyboardInterrupt:
        print("\n\n⏹️  Campaign stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
