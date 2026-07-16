import pytest
from sqlalchemy import select

from app.db import get_db
from app.tables import ApifyAccount, ApifyActorBinding


@pytest.mark.integration
async def test_apify_account_and_binding_are_workspace_scoped(workspace_record):
    async with get_db() as db:
        account = ApifyAccount(
            workspace_id=workspace_record.id,
            label="Compte principal",
            apify_user_id="user-1",
            username="demo",
            token_ciphertext=b"ciphertext",
            token_fingerprint="f" * 64,
            webhook_secret_ciphertext=b"webhook-ciphertext",
            webhook_secret_hash="w" * 64,
        )
        db.add(account)
        await db.flush()
        binding = ApifyActorBinding(
            workspace_id=workspace_record.id,
            account_id=account.id,
            resource_type="actor",
            resource_id="owner/example",
            name="Example",
            enabled=False,
        )
        db.add(binding)

    async with get_db() as db:
        stored = (
            await db.execute(
                select(ApifyActorBinding).where(
                    ApifyActorBinding.resource_id == "owner/example"
                )
            )
        ).scalar_one()
        assert stored.enabled is False
