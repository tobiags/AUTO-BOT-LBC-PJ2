from datetime import UTC, datetime
from uuid import uuid4

from app.models import SmsClassification
from app.services.phone_extractor import extract_phone
from app.services.sms_inbox import classify_sms, normalize_inbound_phone
from app.services.sms_sequence import choose_sms_variant, next_due_at


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
