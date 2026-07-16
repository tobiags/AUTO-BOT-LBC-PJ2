from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db import get_db
from app.services.apify_ingestion import import_run
from app.tables import ApifyActorBinding, ApifyItem, ApifyRun, SmsSequence


@pytest.mark.integration
async def test_import_creates_one_sequence_and_classifies_other_items(
    succeeded_apify_run, monkeypatch
):
    rows = [
        {
            "url": "https://www.leboncoin.fr/ad/1",
            "title": "Clio",
            "phone": "0612345678",
        },
        {
            "url": "https://www.leboncoin.fr/ad/1",
            "title": "Clio",
            "phone": "+33612345678",
        },
        {"title": "Sans telephone"},
    ]

    async def fake_iter_dataset(token, dataset_id):
        assert token.startswith("apify_api_")
        selected = rows if dataset_id == "dataset-test-fixed" else rows[:1]
        for index, item in enumerate(selected):
            yield index, item

    monkeypatch.setattr("app.boundaries.apify_iter_dataset", fake_iter_dataset)

    async with get_db() as db:
        original_binding = await db.get(ApifyActorBinding, succeeded_apify_run.binding_id)
        other_binding = ApifyActorBinding(
            workspace_id=succeeded_apify_run.workspace_id,
            account_id=succeeded_apify_run.account_id,
            campaign_id=original_binding.campaign_id,
            resource_type="actor",
            resource_id=f"owner/other-{uuid4()}",
            name="Other Actor",
            enabled=True,
        )
        db.add(other_binding)
        await db.flush()
        other_run = ApifyRun(
            workspace_id=succeeded_apify_run.workspace_id,
            account_id=succeeded_apify_run.account_id,
            binding_id=other_binding.id,
            apify_run_id=f"run-{uuid4()}",
            status="SUCCEEDED",
            default_dataset_id="dataset-other",
        )
        db.add(other_run)
        await db.flush()
        other_run_id = other_run.id

    with patch("app.tasks.run_sms_sequences_task.delay") as enqueue:
        first = await import_run(succeeded_apify_run.id)
        replay = await import_run(succeeded_apify_run.id)
        other_actor = await import_run(other_run_id)

    assert first == {
        "read": 3,
        "actionable": 2,
        "sequences_created": 1,
        "exceptions": 0,
    }
    assert replay == {
        "read": 3,
        "actionable": 2,
        "sequences_created": 0,
        "exceptions": 0,
    }
    assert other_actor == {
        "read": 1,
        "actionable": 1,
        "sequences_created": 0,
        "exceptions": 0,
    }
    enqueue.assert_called_once_with()
    async with get_db() as db:
        assert await db.scalar(select(func.count()).select_from(ApifyItem)) == 4
        assert await db.scalar(select(func.count()).select_from(SmsSequence)) == 1
