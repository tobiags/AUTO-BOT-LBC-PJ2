from unittest.mock import patch

import pytest

from app.db import get_db
from app.services.apify_learning import (
    compare_profiles,
    create_candidate_profile,
    evaluate_candidate,
    promote_profile,
    rollback_profile,
)
from app.tables import (
    ApifyActorBinding,
    ApifyItem,
    ApifyNormalizationProfile,
)


def test_candidate_is_discarded_when_a_stable_phone_changes():
    baseline = [{"item": "1", "phone": "+33612345678", "status": "actionable"}]
    candidate = [{"item": "1", "phone": "+33699999999", "status": "actionable"}]

    decision = compare_profiles(baseline, candidate, minimum_sample_size=1)

    assert decision.status == "discard"
    assert decision.reason == "stable_phone_regression"


def test_candidate_can_keep_safe_new_coverage():
    baseline = [{"item": "1", "phone": None, "status": "non_actionable"}]
    candidate = [
        {
            "item": "1",
            "phone": "+33612345678",
            "status": "actionable",
            "independent_signals": 2,
        }
    ]

    decision = compare_profiles(baseline, candidate, minimum_sample_size=1)

    assert decision.status == "keep"


def test_candidate_rejects_new_blacklist_violation():
    baseline = [{"item": "1", "phone": None, "blacklisted": False}]
    candidate = [
        {
            "item": "1",
            "phone": "+33612345678",
            "blacklisted": True,
            "independent_signals": 2,
        }
    ]

    decision = compare_profiles(baseline, candidate, minimum_sample_size=1)

    assert decision.reason == "blacklist_regression"


def test_candidate_rejects_increased_ambiguity_and_duplicates():
    baseline = [
        {"item": "1", "status": "actionable"},
        {"item": "2", "status": "actionable"},
    ]
    ambiguous = [
        {"item": "1", "status": "exception"},
        {"item": "2", "status": "actionable"},
    ]
    duplicate = [
        {"item": "1", "status": "duplicate"},
        {"item": "2", "status": "actionable"},
    ]

    assert (
        compare_profiles(baseline, ambiguous, minimum_sample_size=1).reason
        == "ambiguity_regression"
    )
    assert (
        compare_profiles(baseline, duplicate, minimum_sample_size=1).reason
        == "duplicate_regression"
    )


def test_candidate_rejects_unsupported_new_coverage():
    baseline = [{"item": "1", "phone": None}]
    candidate = [{"item": "1", "phone": "+33612345678", "independent_signals": 1}]

    decision = compare_profiles(baseline, candidate, minimum_sample_size=1)

    assert decision.reason == "insufficient_evidence"


@pytest.mark.integration
async def test_candidate_is_evaluated_promoted_and_rolled_back_without_sms(
    succeeded_apify_run,
):
    async with get_db() as db:
        binding = await db.get(ApifyActorBinding, succeeded_apify_run.binding_id)
        active = ApifyNormalizationProfile(
            workspace_id=succeeded_apify_run.workspace_id,
            binding_id=binding.id,
            version=1,
            schema_fingerprint="a" * 64,
            mappings={"phone": "phone"},
            aliases={},
            priorities={},
            thresholds={},
            metrics={},
            status="active",
        )
        db.add(active)
        await db.flush()
        binding.active_profile_id = active.id
        db.add(
            ApifyItem(
                workspace_id=succeeded_apify_run.workspace_id,
                account_id=succeeded_apify_run.account_id,
                run_id=succeeded_apify_run.id,
                dataset_index=0,
                content_hash="b" * 64,
                raw_payload={"phone": "0612345678"},
                status="imported",
            )
        )
        active_id = active.id

    with patch("app.tasks.run_sms_sequences_task.delay") as enqueue:
        candidate = await create_candidate_profile(succeeded_apify_run.binding_id)
        experiment = await evaluate_candidate(candidate.id)
        promoted = await promote_profile(candidate.id)
        rolled_back = await rollback_profile(
            succeeded_apify_run.binding_id,
            active_id,
        )

    assert candidate.mappings == {"phone": "phone"}
    assert experiment.decision == "keep"
    assert promoted.status == "active"
    assert rolled_back.id == active_id
    assert rolled_back.status == "active"
    enqueue.assert_not_called()
