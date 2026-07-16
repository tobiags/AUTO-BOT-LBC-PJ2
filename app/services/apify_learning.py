import hashlib
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select

from app.db import get_db
from app.models import (
    ApifyExperimentView,
    ApifyProfileStatus,
    ApifyProfileView,
)
from app.services.apify_normalizer import (
    collect_candidates,
    normalize_apify_item,
)
from app.services.blacklist import is_blacklisted
from app.tables import (
    ApifyActorBinding,
    ApifyItem,
    ApifyNormalizationExperiment,
    ApifyNormalizationProfile,
    ApifyRun,
)


class ProfileDecision(BaseModel):
    status: Literal["keep", "discard", "crash"]
    reason: str
    metrics: dict[str, float | int]


def _is_ambiguous(row: dict) -> bool:
    return bool(row.get("ambiguous")) or row.get("status") == "exception"


def _is_duplicate(row: dict) -> bool:
    return bool(row.get("duplicate")) or row.get("status") == "duplicate"


def _decision_metrics(baseline: list[dict], candidate: list[dict]) -> dict[str, int]:
    return {
        "sample_size": len(candidate),
        "baseline_coverage": sum(bool(row.get("phone")) for row in baseline),
        "candidate_coverage": sum(bool(row.get("phone")) for row in candidate),
        "baseline_ambiguities": sum(_is_ambiguous(row) for row in baseline),
        "candidate_ambiguities": sum(_is_ambiguous(row) for row in candidate),
        "baseline_duplicates": sum(_is_duplicate(row) for row in baseline),
        "candidate_duplicates": sum(_is_duplicate(row) for row in candidate),
    }


def compare_profiles(
    baseline: list[dict],
    candidate: list[dict],
    *,
    minimum_sample_size: int,
) -> ProfileDecision:
    """Apply hard safety gates before a normalization profile can be promoted."""
    if len(candidate) < minimum_sample_size:
        return ProfileDecision(
            status="discard",
            reason="insufficient_sample",
            metrics={"sample_size": len(candidate)},
        )
    try:
        old = {str(row["item"]): row for row in baseline}
        new = {str(row["item"]): row for row in candidate}
    except (KeyError, TypeError):
        return ProfileDecision(
            status="crash",
            reason="invalid_corpus",
            metrics={"sample_size": len(candidate)},
        )
    if len(old) != len(baseline) or len(new) != len(candidate) or old.keys() != new.keys():
        return ProfileDecision(
            status="crash",
            reason="corpus_mismatch",
            metrics={"sample_size": len(candidate)},
        )

    metrics = _decision_metrics(baseline, candidate)
    changed = sum(
        1
        for item, row in new.items()
        if old[item].get("phone") and old[item].get("phone") != row.get("phone")
    )
    if changed:
        return ProfileDecision(
            status="discard",
            reason="stable_phone_regression",
            metrics={**metrics, "changed_stable_phones": changed},
        )

    blacklist_regressions = sum(
        1
        for item, row in new.items()
        if row.get("phone") and row.get("blacklisted") and not old[item].get("blacklisted")
    )
    if blacklist_regressions:
        return ProfileDecision(
            status="discard",
            reason="blacklist_regression",
            metrics={**metrics, "new_blacklist_violations": blacklist_regressions},
        )
    if metrics["candidate_ambiguities"] > metrics["baseline_ambiguities"]:
        return ProfileDecision(
            status="discard",
            reason="ambiguity_regression",
            metrics=metrics,
        )
    if metrics["candidate_duplicates"] > metrics["baseline_duplicates"]:
        return ProfileDecision(
            status="discard",
            reason="duplicate_regression",
            metrics=metrics,
        )

    unsafe_new = sum(
        1
        for item, row in new.items()
        if not old[item].get("phone") and row.get("phone") and row.get("independent_signals", 0) < 2
    )
    if unsafe_new:
        return ProfileDecision(
            status="discard",
            reason="insufficient_evidence",
            metrics={**metrics, "unsafe_new_coverage": unsafe_new},
        )

    same_results = all(
        old[item].get("phone") == row.get("phone") and old[item].get("status") == row.get("status")
        for item, row in new.items()
    )
    baseline_complexity = max((int(row.get("mapping_count", 0)) for row in baseline), default=0)
    candidate_complexity = max((int(row.get("mapping_count", 0)) for row in candidate), default=0)
    if same_results and candidate_complexity > baseline_complexity:
        return ProfileDecision(
            status="discard",
            reason="complexity_regression",
            metrics={
                **metrics,
                "baseline_mapping_count": baseline_complexity,
                "candidate_mapping_count": candidate_complexity,
            },
        )
    return ProfileDecision(
        status="keep",
        reason="safe_non_regression",
        metrics={
            **metrics,
            "baseline_mapping_count": baseline_complexity,
            "candidate_mapping_count": candidate_complexity,
        },
    )


def _profile_dict(profile: ApifyNormalizationProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "mappings": profile.mappings,
        "aliases": profile.aliases,
        "priorities": profile.priorities,
        "thresholds": profile.thresholds,
    }


async def create_candidate_profile(
    binding_id: UUID,
    inferred_mappings: dict[str, str] | None = None,
) -> ApifyProfileView:
    async with get_db() as db:
        binding = await db.scalar(
            select(ApifyActorBinding).where(ApifyActorBinding.id == binding_id).with_for_update()
        )
        if binding is None:
            raise LookupError("apify_binding_not_found")
        active = (
            await db.get(ApifyNormalizationProfile, binding.active_profile_id)
            if binding.active_profile_id
            else None
        )
        version = (
            await db.scalar(
                select(func.max(ApifyNormalizationProfile.version)).where(
                    ApifyNormalizationProfile.binding_id == binding_id
                )
            )
            or 0
        ) + 1
        mappings = dict(active.mappings if active else {})
        mappings.update(inferred_mappings or {})
        candidate = ApifyNormalizationProfile(
            workspace_id=binding.workspace_id,
            binding_id=binding.id,
            version=version,
            schema_fingerprint=(binding.schema_fingerprint or hashlib.sha256(b"{}").hexdigest()),
            mappings=mappings,
            aliases=dict(active.aliases if active else {}),
            priorities=dict(active.priorities if active else {}),
            thresholds=dict(active.thresholds if active else {}),
            metrics={},
            status=ApifyProfileStatus.CANDIDATE.value,
        )
        db.add(candidate)
        await db.flush()
        await db.refresh(candidate)
        return ApifyProfileView.model_validate(candidate)


def _mark_duplicates(rows: list[dict]) -> None:
    counts = Counter(row.get("phone") for row in rows if row.get("phone"))
    seen: Counter = Counter()
    for row in rows:
        phone = row.get("phone")
        if phone and counts[phone] > 1:
            seen[phone] += 1
            row["duplicate"] = seen[phone] > 1


async def _replay_rows(
    items: list[ApifyItem],
    profile: ApifyNormalizationProfile | None,
) -> list[dict]:
    profile_payload = _profile_dict(profile)
    mapping_count = len(profile_payload["mappings"]) if profile_payload else 0
    rows: list[dict] = []
    for item in items:
        normalized = normalize_apify_item(
            item.raw_payload,
            schema=None,
            profile=profile_payload,
        )
        candidates = collect_candidates(item.raw_payload, None, profile_payload)
        independent_signals = len(
            {
                candidate.path
                for candidate in candidates.get("phone", [])
                if candidate.value == normalized.phone_e164
            }
        )
        rows.append(
            {
                "item": str(item.id),
                "phone": normalized.phone_e164,
                "status": normalized.status,
                "ambiguous": normalized.error_code == "ambiguous_phone",
                "blacklisted": bool(
                    normalized.phone_e164 and await is_blacklisted(normalized.phone_e164)
                ),
                "independent_signals": independent_signals,
                "mapping_count": mapping_count,
            }
        )
    _mark_duplicates(rows)
    return rows


def _summary_metrics(rows: list[dict]) -> dict[str, int]:
    return {
        "sample_size": len(rows),
        "coverage": sum(bool(row.get("phone")) for row in rows),
        "ambiguities": sum(_is_ambiguous(row) for row in rows),
        "duplicates": sum(_is_duplicate(row) for row in rows),
        "blacklist_violations": sum(bool(row.get("blacklisted")) for row in rows),
        "mapping_count": max((int(row.get("mapping_count", 0)) for row in rows), default=0),
    }


async def evaluate_candidate(
    profile_id: UUID,
    *,
    minimum_sample_size: int = 1,
) -> ApifyExperimentView:
    async with get_db() as db:
        candidate = await db.get(ApifyNormalizationProfile, profile_id)
        if candidate is None:
            raise LookupError("apify_profile_not_found")
        if candidate.status != ApifyProfileStatus.CANDIDATE.value:
            raise ValueError("apify_profile_not_candidate")
        binding = await db.get(ApifyActorBinding, candidate.binding_id)
        if binding is None:
            raise LookupError("apify_binding_not_found")
        baseline = (
            await db.get(ApifyNormalizationProfile, binding.active_profile_id)
            if binding.active_profile_id
            else None
        )
        items = list(
            (
                await db.scalars(
                    select(ApifyItem)
                    .join(ApifyRun, ApifyRun.id == ApifyItem.run_id)
                    .where(ApifyRun.binding_id == binding.id)
                    .order_by(ApifyItem.created_at, ApifyItem.id)
                )
            ).all()
        )
        try:
            baseline_rows = await _replay_rows(items, baseline)
            candidate_rows = await _replay_rows(items, candidate)
            decision = compare_profiles(
                baseline_rows,
                candidate_rows,
                minimum_sample_size=minimum_sample_size,
            )
        except Exception as exc:
            baseline_rows = []
            candidate_rows = []
            decision = ProfileDecision(
                status="crash",
                reason=f"replay_failed:{type(exc).__name__}",
                metrics={"sample_size": len(items)},
            )
        experiment = ApifyNormalizationExperiment(
            workspace_id=candidate.workspace_id,
            binding_id=candidate.binding_id,
            baseline_profile_id=baseline.id if baseline else None,
            candidate_profile_id=candidate.id,
            corpus_size=len(items),
            baseline_metrics=_summary_metrics(baseline_rows),
            candidate_metrics={
                **_summary_metrics(candidate_rows),
                **decision.metrics,
            },
            decision=decision.status,
            reason=decision.reason,
            evaluated_at=datetime.now(UTC),
        )
        candidate.metrics = experiment.candidate_metrics
        db.add(experiment)
        await db.flush()
        await db.refresh(experiment)
        return ApifyExperimentView.model_validate(experiment)


async def promote_profile(profile_id: UUID) -> ApifyProfileView:
    async with get_db() as db:
        candidate = await db.scalar(
            select(ApifyNormalizationProfile)
            .where(ApifyNormalizationProfile.id == profile_id)
            .with_for_update()
        )
        if candidate is None:
            raise LookupError("apify_profile_not_found")
        binding = await db.scalar(
            select(ApifyActorBinding)
            .where(ApifyActorBinding.id == candidate.binding_id)
            .with_for_update()
        )
        if binding is None:
            raise LookupError("apify_binding_not_found")
        experiment = await db.scalar(
            select(ApifyNormalizationExperiment)
            .where(ApifyNormalizationExperiment.candidate_profile_id == profile_id)
            .order_by(ApifyNormalizationExperiment.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        if candidate.status != ApifyProfileStatus.CANDIDATE.value:
            raise ValueError("apify_profile_not_candidate")
        if experiment is None or experiment.decision != "keep":
            raise ValueError("apify_profile_not_approved")
        if binding.active_profile_id:
            active = await db.scalar(
                select(ApifyNormalizationProfile)
                .where(ApifyNormalizationProfile.id == binding.active_profile_id)
                .with_for_update()
            )
            if active is not None:
                active.status = ApifyProfileStatus.RETIRED.value
                active.retired_at = datetime.now(UTC)
        candidate.status = ApifyProfileStatus.ACTIVE.value
        candidate.promoted_at = datetime.now(UTC)
        candidate.retired_at = None
        binding.active_profile_id = candidate.id
        await db.flush()
        await db.refresh(candidate)
        return ApifyProfileView.model_validate(candidate)


async def rollback_profile(
    binding_id: UUID,
    profile_id: UUID,
) -> ApifyProfileView:
    async with get_db() as db:
        binding = await db.scalar(
            select(ApifyActorBinding).where(ApifyActorBinding.id == binding_id).with_for_update()
        )
        target = await db.scalar(
            select(ApifyNormalizationProfile)
            .where(ApifyNormalizationProfile.id == profile_id)
            .with_for_update()
        )
        if binding is None:
            raise LookupError("apify_binding_not_found")
        if target is None or target.binding_id != binding.id:
            raise LookupError("apify_profile_not_found")
        if binding.active_profile_id and binding.active_profile_id != target.id:
            active = await db.scalar(
                select(ApifyNormalizationProfile)
                .where(ApifyNormalizationProfile.id == binding.active_profile_id)
                .with_for_update()
            )
            if active is not None:
                active.status = ApifyProfileStatus.RETIRED.value
                active.retired_at = datetime.now(UTC)
        target.status = ApifyProfileStatus.ACTIVE.value
        target.promoted_at = datetime.now(UTC)
        target.retired_at = None
        binding.active_profile_id = target.id
        await db.flush()
        await db.refresh(target)
        return ApifyProfileView.model_validate(target)
