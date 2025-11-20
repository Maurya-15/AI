"""Script to manually trigger campaigns for testing."""

import requests
import sys
import json

BASE_URL = "http://localhost:8000"


def trigger_campaign(campaign_type: str):
    """Trigger a campaign manually."""
    print(f"\n🚀 Triggering {campaign_type} campaign...")
    print("=" * 60)
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/campaigns/trigger/{campaign_type}")
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("success"):
            print(f"✅ {result['message']}")
            print("\n📊 Campaign Report:")
            print("-" * 60)
            
            report = result.get("report", {})
            print(f"Campaign ID: {report.get('campaign_id')}")
            print(f"Type: {report.get('campaign_type')}")
            print(f"Total Attempted: {report.get('total_attempted')}")
            print(f"Total Success: {report.get('total_success')}")
            print(f"Total Failed: {report.get('total_failed')}")
            print(f"Duration: {report.get('duration_seconds', 0):.2f} seconds")
            
            if report.get('errors'):
                print(f"\n⚠️  Errors ({report.get('error_count')}):")
                for error in report.get('errors', [])[:5]:
                    print(f"  - {error}")
            
            print("=" * 60)
            return True
        else:
            print(f"❌ Failed to trigger campaign")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to the server")
        print("   Make sure the application is running on http://localhost:8000")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if e.response:
            print(f"   Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def get_schedule():
    """Get campaign schedule."""
    print("\n📅 Campaign Schedule:")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/campaigns/schedule")
        response.raise_for_status()
        
        result = response.json()
        
        print(f"Scheduler Running: {result.get('scheduler_running')}")
        print(f"\nEmail Campaign:")
        print(f"  Next Run: {result.get('email_campaign', {}).get('next_run', 'Not scheduled')}")
        print(f"\nCall Campaign:")
        print(f"  Next Run: {result.get('call_campaign', {}).get('next_run', 'Not scheduled')}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error getting schedule: {e}")


def main():
    """Main function."""
    print("\n🎯 DevSyncSalesAI - Manual Campaign Trigger")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python trigger_campaign.py email    # Trigger email campaign")
        print("  python trigger_campaign.py schedule # Show campaign schedule")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "schedule":
        get_schedule()
    elif command == "email":
        trigger_campaign("email")
    else:
        print(f"❌ Invalid command: {command}")
        print("   Valid commands: email, schedule")
        sys.exit(1)


if __name__ == "__main__":
    main()
