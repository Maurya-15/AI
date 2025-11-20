"""Simple script to run the DevSyncSalesAI application."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Set environment variables for local testing
os.environ.setdefault('DATABASE_URL', 'sqlite:///./devsync_sales.db')
os.environ.setdefault('DRY_RUN_MODE', 'true')
os.environ.setdefault('APPROVAL_MODE', 'true')

print("=" * 60)
print("DevSyncSalesAI - Starting Application")
print("=" * 60)
print()
print("🚀 API Server: http://localhost:8000")
print("📚 API Docs: http://localhost:8000/docs")
print("❤️  Health Check: http://localhost:8000/health")
print()
print("⚠️  Running in DRY-RUN mode (no actual outreach)")
print("⚠️  Using SQLite database (local testing)")
print()
print("Press Ctrl+C to stop")
print("=" * 60)
print()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
