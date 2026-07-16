from unittest.mock import AsyncMock

import pytest

from app.services.apify_normalizer import (
    flatten_payload,
    normalize_apify_item,
    normalize_apify_item_with_fallback,
)


@pytest.mark.parametrize(
    ("payload", "phone", "title"),
    [
        ({"phone": "06 12 34 56 78", "title": "Clio"}, "+33612345678", "Clio"),
        (
            {
                "seller": {"contactNumber": "+33 7 11 22 33 44"},
                "vehicle": {"name": "208"},
            },
            "+33711223344",
            "208",
        ),
        (
            {
                "description": "Vendeur joignable au 06 98 76 54 32",
                "url": "https://example.test/a",
            },
            "+33698765432",
            None,
        ),
    ],
)
def test_normalizer_recognizes_nested_and_text_values(payload, phone, title):
    result = normalize_apify_item(payload, schema=None, profile=None)
    assert result.phone_e164 == phone
    assert result.title == title


def test_normalizer_flags_equal_phone_candidates():
    result = normalize_apify_item(
        {"phone1": "0612345678", "phone2": "0698765432"},
        schema=None,
        profile=None,
    )
    assert result.status == "exception"
    assert result.error_code == "ambiguous_phone"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"items": [{"nested": [{"value": None}]}]},
        {"mixed": [1, "texte", False, {"phone": object()}]},
    ],
)
def test_arbitrary_nesting_never_raises(payload):
    result = normalize_apify_item(payload, schema=None, profile=None)
    assert result.status in {"actionable", "non_actionable", "rejected", "exception"}


def test_normalizer_evidence_points_to_original_values():
    payload = {"seller": {"phone": "0612345678"}, "vehicle": {"name": "Clio"}}
    result = normalize_apify_item(payload, schema=None, profile=None)
    flattened = flatten_payload(payload)

    assert all(path in flattened for path in result.evidence.values())
    assert result.phone_e164 == "+33612345678"


def test_invalid_phone_never_becomes_actionable():
    result = normalize_apify_item(
        {"phone": "0612", "title": "Invalide"}, schema=None, profile=None
    )
    assert result.status != "actionable"
    assert result.phone_e164 is None


@pytest.mark.asyncio
async def test_ai_fallback_can_only_select_an_existing_path(monkeypatch):
    infer = AsyncMock(return_value={"phone": "phone1"})
    monkeypatch.setattr("app.boundaries.infer_apify_lead_fields", infer)
    monkeypatch.setattr(
        "app.services.apify_normalizer.settings.apify_ai_fallback_enabled", True
    )
    payload = {"phone1": "0612345678", "phone2": "0698765432"}

    result = await normalize_apify_item_with_fallback(
        payload, schema=None, profile=None
    )

    assert result.status == "actionable"
    assert result.phone_e164 == "+33612345678"
