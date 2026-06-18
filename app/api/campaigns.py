import uuid

from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.models import CampaignCreate, CampaignOut
from app.tables import Campaign

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignOut, status_code=201)
async def create_campaign(payload: CampaignCreate):
    async with get_db() as db:
        campaign = Campaign(
            type=payload.type,
            message_template=payload.message_template,
            quota_per_sim=payload.quota_per_sim,
        )
        db.add(campaign)
        await db.flush()
        return CampaignOut.model_validate(campaign)


@router.post("/{campaign_id}/start", tags=["campaigns"])
async def start_campaign(campaign_id: uuid.UUID):
    from app.tasks import run_campaign_task
    run_campaign_task.delay(str(campaign_id))
    return {"queued": True, "campaign_id": str(campaign_id)}


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(campaign_id: uuid.UUID):
    async with get_db() as db:
        campaign = await db.get(Campaign, campaign_id)
        if not campaign:
            raise HTTPException(404, "Campagne introuvable")
        return CampaignOut.model_validate(campaign)
