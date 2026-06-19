"""
Tests unitaires warm_up — fonctions pures et logique de transition.

Les fonctions qui nécessitent la DB sont marquées @pytest.mark.integration.
"""
import pytest

from app.models import DatadomeTrustLevel
from app.services.warm_up import _trust_ge_medium


# ── _trust_ge_medium ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_trust_medium_passes():
    assert _trust_ge_medium(DatadomeTrustLevel.MEDIUM) is True


@pytest.mark.unit
def test_trust_high_passes():
    assert _trust_ge_medium(DatadomeTrustLevel.HIGH) is True


@pytest.mark.unit
def test_trust_low_fails():
    assert _trust_ge_medium(DatadomeTrustLevel.LOW) is False


@pytest.mark.unit
def test_trust_unknown_string_fails():
    assert _trust_ge_medium("UNKNOWN") is False


# ── Constantes de seuil ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_min_age_is_48h():
    from app.services.warm_up import _MIN_AGE_HOURS
    assert _MIN_AGE_HOURS == 48


@pytest.mark.unit
def test_force_eval_is_72h():
    from app.services.warm_up import _FORCE_EVAL_HOURS
    assert _FORCE_EVAL_HOURS == 72


@pytest.mark.unit
def test_quota_max_is_30():
    from app.services.warm_up import _QUOTA_MAX
    assert _QUOTA_MAX == 30


# ── evaluate_warmup_batch (intégration — nécessite DB) ───────────────────────

@pytest.mark.integration
async def test_evaluate_warmup_batch_returns_dict():
    """Vérification minimale : la fonction retourne le bon format."""
    from app.services.warm_up import evaluate_warmup_batch
    result = await evaluate_warmup_batch()
    assert "promoted" in result
    assert "kept" in result
    assert "slowed" in result
    assert all(isinstance(v, int) for v in result.values())


# ── update_account_health (intégration — nécessite DB) ───────────────────────

@pytest.mark.integration
async def test_update_account_health_noop_on_unknown_id():
    """Compte inexistant → ne lève pas d'exception."""
    import uuid

    from app.services.warm_up import update_account_health
    await update_account_health(str(uuid.uuid4()), success=True)
