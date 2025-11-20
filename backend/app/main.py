"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import sys

from app.config import get_settings, validate_production_config
from app import __version__

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="DevSyncSalesAI",
    description="AI-driven compliant business outreach system",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Starting DevSyncSalesAI...")
    
    try:
        settings = get_settings()
        logger.info(f"Configuration loaded successfully")
        logger.info(f"DRY_RUN_MODE: {settings.DRY_RUN_MODE}")
        logger.info(f"APPROVAL_MODE: {settings.APPROVAL_MODE}")
        logger.info(f"DAILY_EMAIL_CAP: {settings.DAILY_EMAIL_CAP}")
        logger.info(f"DAILY_CALL_CAP: {settings.DAILY_CALL_CAP}")
        
        # Display masked configuration
        masked_config = settings.get_masked_config()
        logger.debug(f"Configuration: {masked_config}")
        
        # Validate production configuration if not in dry-run
        if not settings.DRY_RUN_MODE:
            validate_production_config()
            logger.warning("⚠️  PRODUCTION MODE ACTIVE - Real outreach will be performed")
        
        # Display compliance warning
        logger.warning("=" * 80)
        logger.warning("LEGAL COMPLIANCE NOTICE")
        logger.warning("=" * 80)
        logger.warning("This system performs automated outreach to businesses.")
        logger.warning("The operator is responsible for:")
        logger.warning("  - Complying with CAN-SPAM, TRAI, GDPR, and local regulations")
        logger.warning("  - Honoring all opt-out requests immediately")
        logger.warning("  - Only contacting businesses with publicly-listed information")
        logger.warning("  - Maintaining proper email authentication (SPF/DKIM/DMARC)")
        logger.warning("  - Monitoring outreach quality and response rates")
        logger.warning("=" * 80)
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Shutting down DevSyncSalesAI...")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "DevSyncSalesAI",
        "version": __version__,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        settings = get_settings()
        
        # TODO: Add actual health checks for database, redis, etc.
        checks = {
            "api": "healthy",
            "config": "loaded",
            "dry_run_mode": settings.DRY_RUN_MODE,
            "approval_mode": settings.APPROVAL_MODE
        }
        
        return {
            "status": "healthy",
            "checks": checks,
            "version": __version__
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if get_settings().LOG_LEVEL == "DEBUG" else "An error occurred"
        }
    )


# API Router
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import Lead, LeadResponse
from app.db import get_db

api_router = APIRouter(prefix="/api/v1", tags=["api"])

# Lead endpoints
@api_router.get("/leads")
async def get_leads(
    skip: int = 0,
    limit: int = 100,
    verified_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get list of leads."""
    query = db.query(Lead)
    
    if verified_only:
        query = query.filter(Lead.email_verified == True, Lead.phone_verified == True)
    
    leads = query.offset(skip).limit(limit).all()
    return leads

@api_router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get system statistics."""
    from app.models import Lead, OutreachHistory
    from datetime import datetime
    
    total_leads = db.query(Lead).count()
    verified_leads = db.query(Lead).filter(
        Lead.email_verified == True,
        Lead.phone_verified == True
    ).count()
    opted_out = db.query(Lead).filter(Lead.opted_out == True).count()
    
    today = datetime.utcnow().date()
    emails_today = db.query(OutreachHistory).filter(
        OutreachHistory.outreach_type == "email",
        OutreachHistory.attempted_at >= today
    ).count()
    
    return {
        "total_leads": total_leads,
        "verified_leads": verified_leads,
        "opted_out": opted_out,
        "emails_sent_today": emails_today,
        "email_cap": get_settings().DAILY_EMAIL_CAP
    }

@api_router.post("/unsubscribe")
async def unsubscribe(token: str = Query(...)):
    """Process unsubscribe request."""
    from app.opt_out import get_opt_out_manager
    manager = get_opt_out_manager()
    success = await manager.process_unsubscribe_link(token)
    
    if success:
        return {"success": True, "message": "You have been unsubscribed"}
    else:
        raise HTTPException(status_code=400, detail="Failed to process unsubscribe")

app.include_router(api_router)

# Include campaign management router
from app.api.campaigns import router as campaigns_router
app.include_router(campaigns_router, prefix="/api/v1")

# Start scheduler
from app.scheduler import get_scheduler

@app.on_event("startup")
async def startup_scheduler():
    """Start scheduler on startup."""
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

@app.on_event("shutdown")
async def shutdown_scheduler():
    """Stop scheduler on shutdown."""
    scheduler = get_scheduler()
    scheduler.stop()
    logger.info("Scheduler stopped")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
