import pytest


@pytest.mark.parametrize(
    ("current", "action", "expected"),
    [
        ("RUNNING", "pause", "PAUSED"),
        ("PAUSED", "resume", "PENDING"),
        ("RUNNING", "cancel", "CANCELLED"),
        ("FAILED", "retry", "PENDING"),
    ],
)
def test_workflow_transitions(current, action, expected):
    from app.services.workflow_control import workflow_transition

    assert workflow_transition(current, action) == expected


def test_workflow_rejects_completed_pause():
    from app.services.workflow_control import workflow_transition

    with pytest.raises(ValueError, match="Invalid workflow transition"):
        workflow_transition("COMPLETED", "pause")
