import pytest
from pydantic import ValidationError

from app.models import ApifyAccountCreate, ApifyBindingCreate


def test_account_token_is_write_only_input():
    payload = ApifyAccountCreate(label="Principal", token="apify_api_token_123")
    assert payload.token.get_secret_value() == "apify_api_token_123"


def test_binding_requires_one_scheduling_authority():
    with pytest.raises(ValidationError, match="scheduling authority"):
        ApifyBindingCreate(
            account_id="123e4567-e89b-12d3-a456-426614174000",
            resource_type="actor",
            resource_id="owner/demo",
            campaign_id="123e4567-e89b-12d3-a456-426614174001",
            schedule_authority="internal",
            schedule_minutes=None,
        )
