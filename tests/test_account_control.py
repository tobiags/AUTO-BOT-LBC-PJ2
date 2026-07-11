import pytest


@pytest.mark.parametrize(
    ("current", "action", "expected"),
    [
        ("ACTIF", "quarantine", "QUARANTAINE"),
        ("RALENTI", "quarantine", "QUARANTAINE"),
        ("QUARANTAINE", "restore", "EN_CHAUFFE"),
        ("BLOQUÉ", "restore", "EN_CHAUFFE"),
        ("EN_CRÉATION", "warm", "EN_CHAUFFE"),
    ],
)
def test_account_transitions(current, action, expected):
    from app.services.account_control import account_transition

    assert account_transition(current, action) == expected


def test_account_transition_rejects_active_restore():
    from app.services.account_control import account_transition

    with pytest.raises(ValueError, match="Invalid account transition"):
        account_transition("ACTIF", "restore")
