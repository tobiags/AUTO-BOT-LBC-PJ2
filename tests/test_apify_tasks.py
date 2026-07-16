from unittest.mock import AsyncMock, patch

from app.tasks import _apify_circuit_breaker_reason, dispatch_due_apify_bindings_task


@patch("app.tasks.launch_apify_binding_task.delay")
@patch("app.services.apify_runs.get_due_binding_ids", new_callable=AsyncMock)
def test_dispatch_queues_each_due_binding(get_due, delay):
    get_due.return_value = ["binding-1", "binding-2"]

    result = dispatch_due_apify_bindings_task()

    assert result["dispatched"] == 2
    assert delay.call_count == 2
    delay.assert_any_call("binding-1")
    delay.assert_any_call("binding-2")


def test_circuit_breaker_enforces_all_three_safety_thresholds():
    assert (
        _apify_circuit_breaker_reason(
            total=100,
            actionable=89,
            ambiguities=11,
            phone_count=89,
            duplicate_count=0,
            schema_changed=False,
        )
        == "ambiguous_phone_rate"
    )
    assert (
        _apify_circuit_breaker_reason(
            total=10,
            actionable=10,
            ambiguities=0,
            phone_count=10,
            duplicate_count=3,
            schema_changed=False,
        )
        == "duplicate_anomaly"
    )
    assert (
        _apify_circuit_breaker_reason(
            total=10,
            actionable=0,
            ambiguities=0,
            phone_count=0,
            duplicate_count=0,
            schema_changed=True,
        )
        == "schema_changed_without_actionable_items"
    )


def test_circuit_breaker_does_not_trip_at_the_thresholds():
    assert (
        _apify_circuit_breaker_reason(
            total=100,
            actionable=90,
            ambiguities=10,
            phone_count=10,
            duplicate_count=2,
            schema_changed=False,
        )
        is None
    )
