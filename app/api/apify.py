from datetime import UTC, datetime
from typing import Annotated, Any, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import func, select

from app import boundaries
from app.config import get_settings
from app.db import get_db
from app.models import (
    ApifyAccountCreate,
    ApifyAccountOut,
    ApifyBindingCreate,
    ApifyBindingOut,
    ApifyDashboardSummary,
    ApifyExceptionView,
    ApifyExperimentView,
    ApifyItemOut,
    ApifyItemPage,
    ApifyProfileView,
    ApifyRunOut,
    ApifyRunPage,
)
from app.security import require_control_role
from app.services import apify_accounts
from app.services.apify_learning import rollback_profile
from app.services.apify_runs import replay_run
from app.services.apify_secrets import ApifySecretCodec
from app.services.phone_extractor import extract_phone
from app.tables import (
    ApifyAccount,
    ApifyActorBinding,
    ApifyException,
    ApifyItem,
    ApifyNormalizationExperiment,
    ApifyNormalizationProfile,
    ApifyRun,
)

router = APIRouter(prefix="/api/v1/apify", tags=["apify"])
RoleHeader = Annotated[str, Header(alias="X-Operator-Role")]


class ApifyAccountPatch(BaseModel):
    token: SecretStr | None = None
    suspended: bool | None = None


class ApifyBindingPatch(BaseModel):
    enabled: bool | None = None
    account_id: UUID | None = None
    resource_type: Literal["actor", "task"] | None = None
    resource_id: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    sector_id: UUID | None = None
    campaign_id: UUID | None = None
    input: dict[str, Any] | None = None
    schedule_authority: Literal["internal", "apify"] | None = None
    schedule_minutes: int | None = Field(default=None, ge=5, le=10080)


def _service_error(exc: Exception) -> NoReturn:
    if isinstance(exc, LookupError):
        raise HTTPException(404, detail={"code": str(exc)}) from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(403, detail={"code": str(exc)}) from exc
    raise HTTPException(400, detail={"code": str(exc)}) from exc


def _mask_phone(value: str) -> str:
    phone = extract_phone(value)
    if not phone:
        return value
    suffix = phone[-3:]
    return f"{phone[:3]} ** ** ** {suffix[:2]} {suffix[-1]}"


def _redact_phones(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_phones(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact_phones(child) for child in value]
    if isinstance(value, str):
        return _mask_phone(value)
    return value


def _item_output(row: ApifyItem, *, reveal_phones: bool) -> ApifyItemOut:
    output = ApifyItemOut.model_validate(row)
    if reveal_phones:
        return output
    data = output.model_dump()
    data["raw_payload"] = _redact_phones(data["raw_payload"])
    data["normalized_payload"] = _redact_phones(data["normalized_payload"])
    return ApifyItemOut.model_validate(data)


def _safe_exception(row: ApifyException) -> dict[str, Any]:
    output = ApifyExceptionView.model_validate(row).model_dump(mode="json")
    evidence = row.evidence or {}
    output["evidence"] = {
        key: evidence[key]
        for key in (
            "reason",
            "sample_size",
            "ambiguity_rate",
            "duplicate_rate",
            "schema_changed",
        )
        if key in evidence
    }
    return output


@router.get("/accounts", response_model=list[ApifyAccountOut])
async def get_accounts(role: RoleHeader = "viewer"):
    require_control_role(role, "viewer")
    return await apify_accounts.list_accounts()


@router.post(
    "/accounts",
    response_model=ApifyAccountOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_account(payload: ApifyAccountCreate, role: RoleHeader = "viewer"):
    require_control_role(role, "admin")
    try:
        return await apify_accounts.create_account(payload)
    except (LookupError, ValueError, PermissionError) as exc:
        _service_error(exc)


@router.patch("/accounts/{account_id}", response_model=ApifyAccountOut)
async def patch_account(
    account_id: UUID,
    payload: ApifyAccountPatch,
    role: RoleHeader = "viewer",
):
    require_control_role(role, "admin")
    try:
        if payload.token is not None:
            return await apify_accounts.replace_account_token(
                account_id,
                payload.token.get_secret_value(),
            )
        if payload.suspended is True:
            return await apify_accounts.suspend_account(account_id)
        raise ValueError("apify_account_patch_empty")
    except (LookupError, ValueError, PermissionError) as exc:
        _service_error(exc)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: UUID, role: RoleHeader = "viewer"):
    require_control_role(role, "admin")
    try:
        await apify_accounts.delete_account(account_id)
    except (LookupError, ValueError, PermissionError, RuntimeError) as exc:
        _service_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/accounts/{account_id}/probe", response_model=ApifyAccountOut)
async def probe_account(account_id: UUID, role: RoleHeader = "viewer"):
    require_control_role(role, "admin")
    settings = get_settings()
    codec = ApifySecretCodec(
        settings.apify_token_encryption_key,
        settings.secret_key,
    )
    try:
        async with get_db() as db:
            account = await db.get(ApifyAccount, account_id)
            if account is None:
                raise LookupError("apify_account_not_found")
            token = codec.decrypt(account.token_ciphertext)
        identity = await boundaries.apify_validate_token(token)
        async with get_db() as db:
            account = await db.get(ApifyAccount, account_id)
            if account is None:
                raise LookupError("apify_account_not_found")
            account.apify_user_id = str(identity["id"])
            account.username = str(identity.get("username") or identity["id"])
            account.status = "active"
            account.last_checked_at = datetime.now(UTC)
            account.last_error = None
        accounts = await apify_accounts.list_accounts()
        return next(account for account in accounts if account.id == account_id)
    except (LookupError, ValueError, PermissionError, RuntimeError) as exc:
        _service_error(exc)


@router.post("/accounts/{account_id}/catalog/sync")
async def sync_account_catalog(account_id: UUID, role: RoleHeader = "viewer"):
    require_control_role(role, "admin")
    try:
        return await apify_accounts.sync_catalog(account_id)
    except (LookupError, ValueError, PermissionError) as exc:
        _service_error(exc)


@router.get("/bindings", response_model=list[ApifyBindingOut])
async def get_bindings(role: RoleHeader = "viewer"):
    require_control_role(role, "viewer")
    return await apify_accounts.list_bindings()


@router.post(
    "/bindings",
    response_model=ApifyBindingOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_binding(payload: ApifyBindingCreate, role: RoleHeader = "viewer"):
    require_control_role(role, "admin")
    try:
        return await apify_accounts.create_binding(payload)
    except (LookupError, ValueError, PermissionError) as exc:
        _service_error(exc)


@router.patch("/bindings/{binding_id}", response_model=ApifyBindingOut)
async def patch_binding(
    binding_id: UUID,
    payload: ApifyBindingPatch,
    role: RoleHeader = "viewer",
):
    require_control_role(role, "admin")
    try:
        config = payload.model_dump(
            exclude={"enabled"},
            exclude_none=True,
        )
        if config:
            binding = await apify_accounts.update_binding(
                binding_id,
                ApifyBindingCreate.model_validate(config),
            )
        else:
            bindings = await apify_accounts.list_bindings()
            binding = next(
                (item for item in bindings if item.id == binding_id),
                None,
            )
            if binding is None:
                raise LookupError("apify_binding_not_found")
        if payload.enabled is not None and payload.enabled != binding.enabled:
            binding = await apify_accounts.set_binding_enabled(
                binding_id,
                payload.enabled,
            )
        return binding
    except (LookupError, StopIteration, ValueError, PermissionError) as exc:
        _service_error(exc)


@router.post("/bindings/{binding_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_binding(binding_id: UUID, role: RoleHeader = "viewer"):
    require_control_role(role, "operator")
    from app.tasks import launch_apify_binding_task

    launch_apify_binding_task.delay(str(binding_id))
    return {"queued": 1, "binding_id": str(binding_id)}


@router.get("/runs", response_model=ApifyRunPage)
async def get_runs(
    role: RoleHeader = "viewer",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    require_control_role(role, "viewer")
    async with get_db() as db:
        total = await db.scalar(select(func.count()).select_from(ApifyRun)) or 0
        rows = list(
            (
                await db.scalars(
                    select(ApifyRun)
                    .order_by(ApifyRun.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
    return ApifyRunPage(
        items=[ApifyRunOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/runs/{run_id}/replay", status_code=status.HTTP_202_ACCEPTED)
async def replay_apify_run(run_id: UUID, role: RoleHeader = "viewer"):
    require_control_role(role, "operator")
    try:
        return await replay_run(run_id)
    except (LookupError, ValueError, PermissionError) as exc:
        _service_error(exc)


@router.get("/items", response_model=ApifyItemPage)
async def get_items(
    role: RoleHeader = "viewer",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    run_id: UUID | None = None,
):
    require_control_role(role, "viewer")
    query = select(ApifyItem)
    count_query = select(func.count()).select_from(ApifyItem)
    if run_id:
        query = query.where(ApifyItem.run_id == run_id)
        count_query = count_query.where(ApifyItem.run_id == run_id)
    async with get_db() as db:
        total = await db.scalar(count_query) or 0
        rows = list(
            (
                await db.scalars(
                    query.order_by(ApifyItem.created_at.desc()).offset(offset).limit(limit)
                )
            ).all()
        )
    reveal = role.lower() not in {"viewer"}
    return ApifyItemPage(
        items=[_item_output(row, reveal_phones=reveal) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/items/{item_id}", response_model=ApifyItemOut)
async def get_item(item_id: UUID, role: RoleHeader = "viewer"):
    require_control_role(role, "viewer")
    async with get_db() as db:
        row = await db.get(ApifyItem, item_id)
        if row is None:
            raise HTTPException(404, detail={"code": "apify_item_not_found"})
    return _item_output(row, reveal_phones=role.lower() != "viewer")


@router.get("/learning")
async def get_learning(role: RoleHeader = "viewer"):
    require_control_role(role, "viewer")
    async with get_db() as db:
        profiles = list(
            (
                await db.scalars(
                    select(ApifyNormalizationProfile).order_by(
                        ApifyNormalizationProfile.created_at.desc()
                    )
                )
            ).all()
        )
        experiments = list(
            (
                await db.scalars(
                    select(ApifyNormalizationExperiment).order_by(
                        ApifyNormalizationExperiment.created_at.desc()
                    )
                )
            ).all()
        )
        exceptions = list(
            (
                await db.scalars(
                    select(ApifyException)
                    .where(ApifyException.status == "open")
                    .order_by(ApifyException.created_at.desc())
                    .limit(100)
                )
            ).all()
        )
    return {
        "profiles": [
            ApifyProfileView.model_validate(row).model_dump(mode="json") for row in profiles
        ],
        "experiments": [
            ApifyExperimentView.model_validate(row).model_dump(mode="json") for row in experiments
        ],
        "exceptions": [_safe_exception(row) for row in exceptions],
    }


@router.post("/profiles/{profile_id}/rollback", response_model=ApifyProfileView)
async def rollback_apify_profile(profile_id: UUID, role: RoleHeader = "viewer"):
    require_control_role(role, "admin")
    async with get_db() as db:
        profile = await db.get(ApifyNormalizationProfile, profile_id)
        if profile is None:
            raise HTTPException(404, detail={"code": "apify_profile_not_found"})
        binding_id = profile.binding_id
    try:
        return await rollback_profile(binding_id, profile_id)
    except (LookupError, ValueError, PermissionError) as exc:
        _service_error(exc)


@router.get("/summary", response_model=ApifyDashboardSummary)
async def get_summary(role: RoleHeader = "viewer"):
    require_control_role(role, "viewer")
    async with get_db() as db:
        return ApifyDashboardSummary(
            accounts_total=await db.scalar(select(func.count()).select_from(ApifyAccount)) or 0,
            accounts_active=await db.scalar(
                select(func.count())
                .select_from(ApifyAccount)
                .where(ApifyAccount.status == "active")
            )
            or 0,
            bindings_total=await db.scalar(select(func.count()).select_from(ApifyActorBinding))
            or 0,
            bindings_enabled=await db.scalar(
                select(func.count())
                .select_from(ApifyActorBinding)
                .where(ApifyActorBinding.enabled.is_(True))
            )
            or 0,
            runs_running=await db.scalar(
                select(func.count()).select_from(ApifyRun).where(ApifyRun.status == "RUNNING")
            )
            or 0,
            runs_failed=await db.scalar(
                select(func.count())
                .select_from(ApifyRun)
                .where(ApifyRun.status.in_(["FAILED", "ABORTED", "TIMED-OUT"]))
            )
            or 0,
            items_imported=await db.scalar(
                select(func.count()).select_from(ApifyItem).where(ApifyItem.status == "imported")
            )
            or 0,
            exceptions_open=await db.scalar(
                select(func.count())
                .select_from(ApifyException)
                .where(ApifyException.status == "open")
            )
            or 0,
        )
