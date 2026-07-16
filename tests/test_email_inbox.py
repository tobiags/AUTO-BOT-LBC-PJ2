from app.tables import EmailMessage


def test_email_message_table_has_retention_and_idempotency_columns():
    columns = EmailMessage.__table__.c

    assert columns.event_key.unique is True
    assert columns.expires_at.nullable is False
    assert columns.body_plain.nullable is False
