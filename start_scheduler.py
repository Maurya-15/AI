"""Start the scheduler for automatic daily email campaigns."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.config import get_settings

def main():
    """Start the scheduler."""
    settings = get_settings()
    
    print("=" * 70)
    print("📅 DevSyncSalesAI - Automatic Email Scheduler")
    print("=" * 70)
    print()
    print(f"⏰ Scheduled Time: {settings.EMAIL_SEND_TIME} {settings.TIMEZONE}")
    print(f"📧 Daily Email Cap: {settings.DAILY_EMAIL_CAP}")
    print(f"📤 Email From: {settings.EMAIL_FROM}")
    print()
    print("🔄 The scheduler will automatically send emails daily at the scheduled time.")
    print("   Press Ctrl+C to stop the scheduler.")
    print()
    print("=" * 70)
    print()
    
    # Start the application with scheduler
    import subprocess
    subprocess.run([sys.executable, "run_app.py"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Scheduler stopped by user")
        sys.exit(0)
