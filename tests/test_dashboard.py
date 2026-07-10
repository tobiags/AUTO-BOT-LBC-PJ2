from app.db import Base
from app.models import ConnectorState


def test_control_tower_tables_are_registered():
    assert {
        "workflow_runs",
        "connector_status",
        "audit_events",
        "lbc_message_log",
    }.issubset(Base.metadata.tables)


def test_dashboard_actions_prioritize_connector_failures_and_account_shortage():
    from types import SimpleNamespace

    from app.api.dashboard import build_action_items

    connectors = [
        SimpleNamespace(
            name="iproxy",
            status=ConnectorState.MISCONFIGURED,
            error_code="HTTP_401",
            error_summary="unauthorized",
        )
    ]

    actions = build_action_items(
        connectors,
        accounts_active=2,
        accounts_minimum=3,
    )

    assert [action.code for action in actions] == [
        "connector.iproxy.HTTP_401",
        "accounts.pool_below_minimum",
    ]
    assert actions[0].severity == "critical"
