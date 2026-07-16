import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import boundaries
from app.config import get_settings
from app.db import get_db
from app.models import ApifyItemStatus, ListingSource
from app.services.apify_normalizer import normalize_apify_item_with_fallback
from app.services.apify_secrets import ApifySecretCodec
from app.services.sms_sequence import ensure_contact_sequence_in_session
from app.tables import (
    ApifyAccount,
    ApifyActorBinding,
    ApifyException,
    ApifyItem,
    ApifyNormalizationProfile,
    ApifyRun,
    Listing,
)


@dataclass(frozen=True)
class _RunContext:
    id: UUID
    workspace_id: UUID
    account_id: UUID
    binding_id: UUID
    campaign_id: UUID
    sector_id: UUID | None
    dataset_id: str
    token: str
    profile: dict[str, Any] | None


@dataclass(frozen=True)
class _ItemOutcome:
    status: str
    sequence_created: bool = False


def _codec() -> ApifySecretCodec:
    settings = get_settings()
    return ApifySecretCodec(
        settings.apify_token_encryption_key,
        settings.secret_key,
    )


def _canonical_payload(payload: Any) -> tuple[dict[str, Any], str]:
    stored = payload if isinstance(payload, dict) else {"value": payload}
    encoded = json.dumps(
        stored,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return stored, hashlib.sha256(encoded.encode()).hexdigest()


def _profile_payload(profile: ApifyNormalizationProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "mappings": profile.mappings,
        "aliases": profile.aliases,
        "priorities": profile.priorities,
        "thresholds": profile.thresholds,
    }


async def _load_run_context(run_id: UUID) -> _RunContext:
    async with get_db() as db:
        row = (
            await db.execute(
                select(ApifyRun, ApifyAccount, ApifyActorBinding)
                .join(ApifyAccount, ApifyAccount.id == ApifyRun.account_id)
                .join(ApifyActorBinding, ApifyActorBinding.id == ApifyRun.binding_id)
                .where(ApifyRun.id == run_id)
            )
        ).one_or_none()
        if row is None:
            raise LookupError("apify_run_not_found")
        run, account, binding = row
        if run.status != "SUCCEEDED" or not run.default_dataset_id:
            raise ValueError("apify_run_not_importable")
        if binding.campaign_id is None:
            raise ValueError("apify_binding_campaign_required")
        profile = (
            await db.get(ApifyNormalizationProfile, binding.active_profile_id)
            if binding.active_profile_id
            else None
        )
        return _RunContext(
            id=run.id,
            workspace_id=run.workspace_id,
            account_id=run.account_id,
            binding_id=run.binding_id,
            campaign_id=binding.campaign_id,
            sector_id=binding.sector_id,
            dataset_id=run.default_dataset_id,
            token=_codec().decrypt(account.token_ciphertext),
            profile=_profile_payload(profile),
        )


async def _insert_or_load_item(
    db: AsyncSession,
    context: _RunContext,
    index: int,
    payload: dict[str, Any],
    content_hash: str,
) -> tuple[ApifyItem, bool]:
    inserted_id = (
        await db.execute(
            pg_insert(ApifyItem)
            .values(
                workspace_id=context.workspace_id,
                account_id=context.account_id,
                run_id=context.id,
                dataset_index=index,
                content_hash=content_hash,
                raw_payload=payload,
                status=ApifyItemStatus.PENDING.value,
            )
            .on_conflict_do_nothing(constraint="uq_apify_dataset_item")
            .returning(ApifyItem.id)
        )
    ).scalar_one_or_none()
    if inserted_id is not None:
        item = await db.get(ApifyItem, inserted_id)
        assert item is not None
        return item, True
    item = await db.scalar(
        select(ApifyItem).where(
            ApifyItem.account_id == context.account_id,
            ApifyItem.run_id == context.id,
            ApifyItem.dataset_index == index,
            ApifyItem.content_hash == content_hash,
        )
    )
    if item is None:
        raise RuntimeError("apify_item_conflict_without_row")
    return item, False


def _replayed_outcome(item: ApifyItem) -> _ItemOutcome:
    if item.status == ApifyItemStatus.IMPORTED.value:
        return _ItemOutcome("actionable")
    if item.status == ApifyItemStatus.EXCEPTION.value:
        return _ItemOutcome("exception")
    return _ItemOutcome("ignored")


async def _upsert_listing(
    db: AsyncSession,
    context: _RunContext,
    normalized,
    payload: dict[str, Any],
) -> Listing | None:
    sources = {
        "leboncoin": ListingSource.LBC,
        "la_centrale": ListingSource.LA_CENTRALE,
    }
    source = sources.get(normalized.source_platform)
    if not normalized.url or source is None:
        return None
    listing = await db.scalar(select(Listing).where(Listing.url == normalized.url))
    if listing is None:
        listing = Listing(
            source=source,
            url=normalized.url,
            sector_id=context.sector_id,
            campaign_id=context.campaign_id,
            title=normalized.title,
            price=normalized.price,
            km=normalized.mileage,
            location=normalized.location,
            phone=normalized.phone_e164,
            raw_data=json.dumps(payload, ensure_ascii=False, default=str),
            make=normalized.brand,
            model=normalized.model,
            year=normalized.year,
        )
        db.add(listing)
        await db.flush()
        return listing
    listing.campaign_id = listing.campaign_id or context.campaign_id
    listing.sector_id = listing.sector_id or context.sector_id
    listing.title = listing.title or normalized.title
    listing.phone = listing.phone or normalized.phone_e164
    return listing


def _sequence_context(normalized) -> dict[str, Any]:
    return {
        key: value
        for key, value in normalized.model_dump(
            exclude={"phone_e164", "evidence", "error_code", "status"}
        ).items()
        if value is not None
    }


async def _process_new_item(
    db: AsyncSession,
    context: _RunContext,
    item: ApifyItem,
    payload: dict[str, Any],
) -> _ItemOutcome:
    normalized = await normalize_apify_item_with_fallback(
        payload,
        schema=None,
        profile=context.profile,
    )
    item.normalized_payload = normalized.model_dump(mode="json")
    item.confidence = normalized.confidence
    item.processed_at = datetime.now(UTC)
    if normalized.status == "exception":
        item.status = ApifyItemStatus.EXCEPTION.value
        item.error = normalized.error_code
        db.add(
            ApifyException(
                workspace_id=context.workspace_id,
                binding_id=context.binding_id,
                run_id=context.id,
                item_id=item.id,
                category=normalized.error_code or "normalization_ambiguity",
                evidence={"paths": normalized.evidence},
            )
        )
        return _ItemOutcome("exception")
    if normalized.status != "actionable" or not normalized.phone_e164:
        item.status = ApifyItemStatus.IGNORED.value
        item.error = normalized.error_code
        return _ItemOutcome("ignored")

    listing = await _upsert_listing(db, context, normalized, payload)
    result = await ensure_contact_sequence_in_session(
        db,
        phone=normalized.phone_e164,
        campaign_id=context.campaign_id,
        listing_id=listing.id if listing else None,
        context=_sequence_context(normalized),
    )
    item.status = ApifyItemStatus.IMPORTED.value
    if result.get("contact_id"):
        item.contact_id = UUID(result["contact_id"])
    if result.get("sequence_id"):
        item.sms_sequence_id = UUID(result["sequence_id"])
    if listing is not None:
        item.listing_id = listing.id
        if result.get("contact_id"):
            listing.contact_id = UUID(result["contact_id"])
    return _ItemOutcome("actionable", bool(result.get("created")))


async def _import_one_item(
    context: _RunContext,
    index: int,
    raw_payload: Any,
) -> _ItemOutcome:
    payload, content_hash = _canonical_payload(raw_payload)
    async with get_db() as db:
        item, inserted = await _insert_or_load_item(
            db,
            context,
            index,
            payload,
            content_hash,
        )
        if not inserted:
            return _replayed_outcome(item)
        try:
            async with db.begin_nested():
                return await _process_new_item(db, context, item, payload)
        except Exception as exc:
            item.status = ApifyItemStatus.IGNORED.value
            item.error = f"item_processing_failed:{type(exc).__name__}"
            item.processed_at = datetime.now(UTC)
            return _ItemOutcome("ignored")


async def _save_run_progress(
    run_id: UUID,
    counters: dict[str, int],
    *,
    finished: bool,
) -> None:
    async with get_db() as db:
        run = await db.get(ApifyRun, run_id)
        if run is None:
            raise LookupError("apify_run_not_found")
        run.items_read = counters["read"]
        run.items_imported = counters["actionable"]
        run.items_exception = counters["exceptions"]
        run.items_ignored = counters["read"] - counters["actionable"] - counters["exceptions"]
        if finished:
            run.imported_at = datetime.now(UTC)


async def import_run(run_id: UUID) -> dict[str, int]:
    """Import every dataset item without allowing one bad item to abort the run."""
    counters = {
        "read": 0,
        "actionable": 0,
        "sequences_created": 0,
        "exceptions": 0,
    }
    context = await _load_run_context(run_id)
    page_size = max(1, get_settings().apify_import_page_size)
    async for index, payload in boundaries.apify_iter_dataset(
        context.token,
        context.dataset_id,
    ):
        outcome = await _import_one_item(context, index, payload)
        counters["read"] += 1
        counters["actionable"] += int(outcome.status == "actionable")
        counters["sequences_created"] += int(outcome.sequence_created)
        counters["exceptions"] += int(outcome.status == "exception")
        if counters["read"] % page_size == 0:
            await _save_run_progress(run_id, counters, finished=False)
    await _save_run_progress(run_id, counters, finished=True)
    if counters["sequences_created"]:
        from app.tasks import run_sms_sequences_task

        run_sms_sequences_task.delay()
    return counters


async def import_remote_run(
    account_id: UUID,
    remote_run_id: str,
) -> dict[str, int]:
    from app.services.apify_runs import get_or_sync_remote_run

    run = await get_or_sync_remote_run(account_id, remote_run_id)
    return await import_run(run.id)
