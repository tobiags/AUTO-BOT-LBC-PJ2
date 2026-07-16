from datetime import UTC, datetime, timedelta

import pytest

from app.db import get_db
from app.services.apify_runs import get_due_binding_ids
from app.tables import ApifyActorBinding


@pytest.mark.integration
async def test_due_bindings_include_only_enabled_internal_schedules(
    configured_apify_binding,
):
    now = datetime.now(UTC)
    async with get_db() as db:
        binding = await db.get(ApifyActorBinding, configured_apify_binding.id)
        binding.schedule_authority = "internal"
        binding.next_run_at = now - timedelta(minutes=1)
        binding.enabled = True

    due = await get_due_binding_ids(now)

    assert configured_apify_binding.id in due
