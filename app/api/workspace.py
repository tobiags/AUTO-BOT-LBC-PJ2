"""Workspace, users and sector resources for the shared dashboard space."""

import hashlib
import hmac
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select

from app.db import get_db
from app.models import (
    SectorCreate,
    SectorOut,
    SectorResourceAssignment,
    UserCreate,
    UserCreated,
    UserLogin,
    UserOut,
)
from app.tables import (
    PlatformAccount,
    Sector,
    SectorAccount,
    SectorProxy,
    SectorSim,
    User,
    Workspace,
)

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])


def _require_role(role: str, minimum: str) -> None:
    rank = {"operateur": 1, "manager": 2, "administrateur": 3}
    if rank.get(role, 0) < rank[minimum]:
        raise HTTPException(403, detail={"code": "INSUFFICIENT_ROLE"})


async def _get_workspace(db):
    workspace = (
        await db.execute(select(Workspace).order_by(Workspace.created_at).limit(1))
    ).scalar_one_or_none()
    if workspace:
        return workspace
    workspace = Workspace(name="AutoTransfert")
    db.add(workspace)
    await db.flush()
    return workspace


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${salt.hex()}${digest.hex()}"


def _password_matches(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


@router.post("/users", response_model=UserCreated, status_code=201)
async def create_user(
    payload: UserCreate,
    x_operator_role: Annotated[str, Header()] = "operateur",
):
    _require_role(x_operator_role, "administrateur")
    temporary_password = secrets.token_urlsafe(12)
    async with get_db() as db:
        workspace = await _get_workspace(db)
        email = payload.email.lower()
        existing = (
            await db.execute(
                select(User).where(User.workspace_id == workspace.id, User.email == email)
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(409, detail={"code": "USER_ALREADY_EXISTS"})
        user = User(
            workspace_id=workspace.id,
            email=email,
            display_name=payload.display_name,
            role=payload.role.value,
            password_hash=_password_hash(temporary_password),
        )
        db.add(user)
        await db.flush()
        return UserCreated.model_validate(
            {**UserOut.model_validate(user).model_dump(), "temporary_password": temporary_password}
        )


@router.post("/authenticate", response_model=UserOut)
async def authenticate_user(payload: UserLogin):
    async with get_db() as db:
        workspace = await _get_workspace(db)
        user = (
            await db.execute(
                select(User).where(
                    User.workspace_id == workspace.id,
                    User.email == payload.email.lower(),
                    User.active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if user is None or not _password_matches(payload.password, user.password_hash):
            raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS"})
        return user


@router.get("/users", response_model=list[UserOut])
async def list_users(x_operator_role: Annotated[str, Header()] = "operateur"):
    _require_role(x_operator_role, "operateur")
    async with get_db() as db:
        workspace = await _get_workspace(db)
        users = (
            (
                await db.execute(
                    select(User).where(User.workspace_id == workspace.id).order_by(User.created_at)
                )
            )
            .scalars()
            .all()
        )
        return users


@router.post("/sectors", response_model=SectorOut, status_code=201)
async def create_sector(
    payload: SectorCreate,
    x_operator_role: Annotated[str, Header()] = "operateur",
):
    _require_role(x_operator_role, "operateur")
    async with get_db() as db:
        workspace = await _get_workspace(db)
        if (
            await db.execute(
                select(Sector).where(
                    Sector.workspace_id == workspace.id, Sector.name == payload.name
                )
            )
        ).scalar_one_or_none():
            raise HTTPException(409, detail={"code": "SECTOR_ALREADY_EXISTS"})
        sector = Sector(workspace_id=workspace.id, **payload.model_dump())
        db.add(sector)
        await db.flush()
        return sector


@router.get("/sectors", response_model=list[SectorOut])
async def list_sectors(x_operator_role: Annotated[str, Header()] = "operateur"):
    _require_role(x_operator_role, "operateur")
    async with get_db() as db:
        workspace = await _get_workspace(db)
        return (
            (
                await db.execute(
                    select(Sector)
                    .where(Sector.workspace_id == workspace.id)
                    .order_by(Sector.created_at)
                )
            )
            .scalars()
            .all()
        )


@router.post("/sectors/{sector_id}/resources", response_model=SectorOut)
async def assign_sector_resources(
    sector_id: UUID,
    payload: SectorResourceAssignment,
    x_operator_role: Annotated[str, Header()] = "operateur",
):
    _require_role(x_operator_role, "manager")
    async with get_db() as db:
        sector = (
            await db.execute(select(Sector).where(Sector.id == sector_id).with_for_update())
        ).scalar_one_or_none()
        if sector is None:
            raise HTTPException(404, detail={"code": "SECTOR_NOT_FOUND"})
        accounts = (
            (
                await db.execute(
                    select(PlatformAccount).where(PlatformAccount.id.in_(payload.account_ids))
                )
            )
            .scalars()
            .all()
        )
        if len(accounts) != len(set(payload.account_ids)):
            raise HTTPException(400, detail={"code": "UNKNOWN_ACCOUNT"})
        await db.execute(
            SectorAccount.__table__.delete().where(SectorAccount.sector_id == sector_id)
        )
        await db.execute(SectorSim.__table__.delete().where(SectorSim.sector_id == sector_id))
        await db.execute(SectorProxy.__table__.delete().where(SectorProxy.sector_id == sector_id))
        db.add_all(
            [
                SectorAccount(
                    sector_id=sector_id,
                    account_id=account_id,
                    daily_limit=payload.daily_limit_per_account,
                )
                for account_id in payload.account_ids
            ]
        )
        db.add_all(
            [
                SectorSim(
                    sector_id=sector_id, sim_id=sim_id, daily_limit=payload.daily_limit_per_sim
                )
                for sim_id in payload.sim_ids
            ]
        )
        db.add_all(
            [SectorProxy(sector_id=sector_id, proxy_id=proxy_id) for proxy_id in payload.proxy_ids]
        )
        return sector
