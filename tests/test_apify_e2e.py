from datetime import UTC, datetime

import pytest


@pytest.mark.integration
async def test_apify_dataset_to_sms_is_idempotent_and_hour_safe(
    monkeypatch, mock_send_sms, succeeded_apify_run
):
    from sqlalchemy import func, select

    from app.db import get_db
    from app.services.apify_ingestion import import_run
    from app.services.sms_sequence import run_due_sms_sequences
    from app.tables import ApifyException, ApifyItem, SmsSequence

    rows = [
        {
            "seller": {"phone": "0612345678"},
            "title": "Clio",
            "url": "https://www.leboncoin.fr/ad/1",
        },
        {
            "seller": {"phone": "+33612345678"},
            "title": "Clio copie",
            "url": "https://www.leboncoin.fr/ad/2",
        },
        {"description": "aucun contact"},
        {"phoneA": "0611111111", "phoneB": "0622222222"},
    ]

    async def fake_iter_dataset(token, dataset_id):
        for index, item in enumerate(rows):
            yield index, item

    monkeypatch.setattr("app.boundaries.apify_iter_dataset", fake_iter_dataset)

    await import_run(succeeded_apify_run.id)
    await run_due_sms_sequences(now=datetime(2026, 7, 16, 3, 0, tzinfo=UTC))
    assert mock_send_sms.await_count == 0

    await import_run(succeeded_apify_run.id)
    await run_due_sms_sequences(now=datetime(2026, 7, 16, 9, 0, tzinfo=UTC))
    assert mock_send_sms.await_count == 1

    async with get_db() as db:
        assert await db.scalar(select(func.count()).select_from(SmsSequence)) == 1
        assert await db.scalar(select(func.count()).select_from(ApifyException)) == 1
        assert await db.scalar(select(func.count()).select_from(ApifyItem)) == 4
