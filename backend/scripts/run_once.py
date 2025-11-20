"""Run a one-time campaign manually."""

import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.scheduler import get_scheduler

async def run_campaign():
    """Run email campaign once."""
    print("Starting manual campaign execution...")
    
    scheduler = get_scheduler()
    await scheduler.execute_email_campaign()
    
    print("Campaign execution complete!")

if __name__ == "__main__":
    asyncio.run(run_campaign())
