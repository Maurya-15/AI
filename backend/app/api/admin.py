"""Admin API endpoints for database management."""

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends
import logging

from app.db import get_db
from app.models import Lead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed-leads")
async def seed_leads(db: Session = Depends(get_db)):
    """Seed database with 100 business leads."""
    
    try:
        # Check if leads already exist
        existing_count = db.query(Lead).count()
        
        if existing_count >= 100:
            return {
                "message": "Database already has leads",
                "existing_count": existing_count,
                "action": "skipped"
            }
        
        # Generate 99 placeholder businesses
        cities = ["Bangalore", "Mumbai", "Delhi", "Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad"]
        categories = ["IT Services", "Digital Marketing", "E-commerce", "Consulting", "Software Development", "Web Design"]
        
        business_leads = []
        
        for i in range(1, 100):
            business_leads.append(Lead(
                source="google_maps",
                business_name=f"Business Solutions {i}",
                primary_email=f"contact{i}@business{i}.com",
                city=cities[i % len(cities)],
                category=categories[i % len(categories)],
                email_verified=True,
                phone_verified=False,
                verification_confidence=0.95,
                raw_metadata={}
            ))
        
        # Add demo contact as #100
        business_leads.append(Lead(
            source="google_maps",
            business_name="Demo Test Company",
            primary_email="anshum25506@gmail.com",
            city="Test City",
            category="Technology",
            email_verified=True,
            phone_verified=False,
            verification_confidence=1.0,
            raw_metadata={"demo": True}
        ))
        
        # Add all leads
        db.add_all(business_leads)
        db.commit()
        
        total_count = db.query(Lead).count()
        
        logger.info(f"Seeded {len(business_leads)} leads to database")
        
        return {
            "message": "Successfully seeded database",
            "leads_added": len(business_leads),
            "total_leads": total_count,
            "action": "completed"
        }
        
    except Exception as e:
        logger.error(f"Error seeding leads: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to seed leads: {str(e)}")


@router.delete("/clear-leads")
async def clear_leads(db: Session = Depends(get_db)):
    """Clear all leads from database (use with caution!)."""
    
    try:
        count = db.query(Lead).count()
        db.query(Lead).delete()
        db.commit()
        
        logger.warning(f"Cleared {count} leads from database")
        
        return {
            "message": "All leads cleared",
            "leads_deleted": count,
            "action": "completed"
        }
        
    except Exception as e:
        logger.error(f"Error clearing leads: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear leads: {str(e)}")


@router.get("/stats")
async def get_admin_stats(db: Session = Depends(get_db)):
    """Get database statistics."""
    
    from app.models import Campaign, OutreachHistory
    
    total_leads = db.query(Lead).count()
    verified_leads = db.query(Lead).filter(Lead.email_verified == True).count()
    opted_out = db.query(Lead).filter(Lead.opted_out == True).count()
    total_campaigns = db.query(Campaign).count()
    total_emails = db.query(OutreachHistory).filter(OutreachHistory.outreach_type == "email").count()
    
    return {
        "leads": {
            "total": total_leads,
            "verified": verified_leads,
            "opted_out": opted_out
        },
        "campaigns": {
            "total": total_campaigns
        },
        "emails": {
            "total_sent": total_emails
        }
    }
