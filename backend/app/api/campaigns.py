"""Campaign management API endpoints."""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

from app.scheduler import get_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("/trigger/{campaign_type}")
async def trigger_campaign(campaign_type: str) -> Dict[str, Any]:
    """
    Manually trigger a campaign for testing.
    
    Args:
        campaign_type: 'email' or 'call'
        
    Returns:
        Campaign execution report
    """
    if campaign_type not in ["email", "call"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid campaign type. Must be 'email' or 'call'"
        )
    
    logger.info(f"Manual trigger requested for {campaign_type} campaign")
    
    try:
        scheduler = get_scheduler()
        report = await scheduler.trigger_manual_campaign(campaign_type)
        
        if report is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to execute {campaign_type} campaign"
            )
        
        return {
            "success": True,
            "message": f"{campaign_type.capitalize()} campaign executed successfully",
            "report": report.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Error triggering {campaign_type} campaign: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error executing campaign: {str(e)}"
        )


@router.get("/schedule")
async def get_schedule() -> Dict[str, Any]:
    """
    Get next scheduled run times for campaigns.
    
    Returns:
        Next run times for email and call campaigns
    """
    try:
        scheduler = get_scheduler()
        next_times = scheduler.get_next_run_times()
        
        return {
            "email_campaign": {
                "next_run": next_times["email"].isoformat() if next_times["email"] else None
            },
            "call_campaign": {
                "next_run": next_times["call"].isoformat() if next_times["call"] else None
            },
            "scheduler_running": scheduler.is_running()
        }
        
    except Exception as e:
        logger.error(f"Error getting schedule: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving schedule: {str(e)}"
        )


@router.get("/status")
async def get_campaign_status() -> Dict[str, Any]:
    """
    Get current campaign execution status.
    
    Returns:
        Status of running campaigns
    """
    try:
        scheduler = get_scheduler()
        
        return {
            "scheduler_running": scheduler.is_running(),
            "email_campaign_running": scheduler._running_campaigns.get("email", False),
            "call_campaign_running": scheduler._running_campaigns.get("call", False)
        }
        
    except Exception as e:
        logger.error(f"Error getting campaign status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving status: {str(e)}"
        )
