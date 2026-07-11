import pytest


@pytest.mark.parametrize(
    ("current", "action", "expected"),
    [
        ("PENDING", "start", "RUNNING"),
        ("RUNNING", "pause", "PAUSED"),
        ("PAUSED", "resume", "RUNNING"),
        ("RUNNING", "cancel", "CANCELLED"),
        ("FAILED", "retry", "RUNNING"),
    ],
)
def test_campaign_command_transitions(current, action, expected):
    from app.services.campaign_control import campaign_transition

    assert campaign_transition(current, action) == expected


def test_campaign_command_rejects_invalid_transition():
    from app.services.campaign_control import campaign_transition

    with pytest.raises(ValueError, match="Invalid campaign transition"):
        campaign_transition("COMPLETED", "resume")
