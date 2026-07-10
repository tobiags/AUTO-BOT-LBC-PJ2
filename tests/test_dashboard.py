from app.db import Base


def test_control_tower_tables_are_registered():
    assert {
        "workflow_runs",
        "connector_status",
        "audit_events",
        "lbc_message_log",
    }.issubset(Base.metadata.tables)
