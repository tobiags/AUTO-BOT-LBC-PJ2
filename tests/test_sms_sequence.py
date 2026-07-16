from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models import SmsClassification
from app.services.phone_extractor import extract_phone
from app.services.sms_inbox import classify_sms, normalize_inbound_phone
from app.services.sms_sequence import (
    choose_sms_variant,
    ensure_contact_sequence,
    next_due_at,
    run_due_sms_sequences,
)


def test_phone_is_normalized_to_e164():
    assert extract_phone("Appelez-moi au 06 12 34 56 78") == "+33612345678"
    assert normalize_inbound_phone("+33 6 12 34 56 78") == "+33612345678"


def test_sms_classification_stops_on_stop_and_detects_information():
    assert classify_sms("STOP") == SmsClassification.STOP
    assert classify_sms("Quel est votre prix ?") == SmsClassification.INFORMATION
    assert classify_sms("Bonjour") == SmsClassification.AMBIGUOUS


def test_sequence_variant_and_schedule_are_deterministic():
    sequence_id = uuid4()
    assert choose_sms_variant(3, sequence_id) == choose_sms_variant(3, sequence_id)
    created = datetime(2026, 7, 13, tzinfo=UTC)
    assert (next_due_at(1, created) - created).days == 7


@pytest.mark.integration
async def test_generic_lead_creates_one_sequence_per_contact_campaign(running_campaign):
    first = await ensure_contact_sequence(
        phone="06 12 34 56 78",
        campaign_id=running_campaign.id,
        context={"title": "Lead Apify", "url": ""},
    )
    second = await ensure_contact_sequence(
        phone="+33612345678",
        campaign_id=running_campaign.id,
        context={"title": "Lead enrichi", "url": ""},
    )
    assert first["sequence_id"] == second["sequence_id"]


@patch("app.boundaries.send_sms", new_callable=AsyncMock)
async def test_due_sequence_does_not_send_outside_paris_window(send_sms):
    result = await run_due_sms_sequences(
        now=datetime(2026, 7, 16, 3, 0, tzinfo=UTC)
    )
    assert result["status"] == "outside_window"
    send_sms.assert_not_awaited()
