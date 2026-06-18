import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import get_db
from app.models import AccountOut, AccountStatus
from app.tables import PlatformAccount

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts():
    async with get_db() as db:
        result = await db.execute(select(PlatformAccount).order_by(PlatformAccount.date_creation.desc()))
        return [AccountOut.model_validate(a) for a in result.scalars()]


@router.patch("/{account_id}/status")
async def update_account_status(account_id: uuid.UUID, status: AccountStatus):
    async with get_db() as db:
        account = await db.get(PlatformAccount, account_id)
        if not account:
            raise HTTPException(404, "Compte introuvable")
        account.status = status
        await db.flush()
        return {"id": str(account_id), "status": status}


@router.post("/trigger-creation")
async def trigger_account_creation(mode: str = "A"):
    """Déclenche manuellement la création d'un nouveau compte LBC."""
    from app.tasks import create_account_task
    task = create_account_task.delay(mode=mode)
    return {"task_id": task.id, "mode": mode}
