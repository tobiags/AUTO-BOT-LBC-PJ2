from unittest.mock import AsyncMock, patch

import pytest

from app.models import ApifyAccountCreate, ApifyBindingCreate
from app.services.apify_accounts import create_account, create_binding


@pytest.mark.integration
@patch("app.boundaries.apify_validate_token", new_callable=AsyncMock)
async def test_create_account_validates_and_never_returns_token(validate):
    validate.return_value = {"id": "user-1", "username": "owner"}
    account = await create_account(
        ApifyAccountCreate(label="Principal", token="apify_api_secret")
    )

    assert account.username == "owner"
    assert account.token_masked == "apif...cret"
    assert not hasattr(account, "token")


@pytest.mark.integration
async def test_binding_rejects_inactive_campaign(
    existing_apify_account, pending_campaign
):
    with pytest.raises(ValueError, match="campaign_not_running"):
        await create_binding(
            ApifyBindingCreate(
                account_id=existing_apify_account.id,
                resource_type="actor",
                resource_id="owner/demo",
                campaign_id=pending_campaign.id,
                schedule_authority="internal",
                schedule_minutes=60,
            )
        )
