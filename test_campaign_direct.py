"""Direct test of campaign execution."""

import sys
import os
import asyncio

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.scheduler import get_scheduler
from app.db import init_db

async def test_campaign():
    """Test campaign execution directly."""
    print("🔧 Initializing...")
    init_db()
    
    print("📧 Testing email campaign...")
    scheduler = get_scheduler()
    
    try:
        report = await scheduler.execute_email_campaign()
        
        if report:
            print("\n✅ Campaign executed successfully!")
            print(f"Campaign ID: {report.campaign_id}")
            print(f"Type: {report.campaign_type}")
            print(f"Attempted: {report.total_attempted}")
            print(f"Success: {report.total_success}")
            print(f"Failed: {report.total_failed}")
            duration = (report.completed_at - report.started_at).total_seconds()
            print(f"Duration: {duration:.2f}s")
        else:
            print("\n❌ Campaign returned None")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_campaign())
