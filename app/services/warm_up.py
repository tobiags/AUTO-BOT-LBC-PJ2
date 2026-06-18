"""
Service de warm-up — transition EN_CHAUFFE → ACTIF / RALENTI.

Règles R04/R05 :
  - Âge compte >= 48h minimum (DataDome warm-up)
  - DatadomeTrustLevel >= MEDIUM requis pour ACTIF
  - score_sante >= 70 et erreurs_24h <= 3
  - Quota progressif : +5 msg/j à chaque promotion, max 30

Appelé par la tâche Celery check_account_pool_task (toutes les heures).
"""
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.db import get_db
from app.models import AccountStatus, DatadomeTrustLevel
from app.tables import PlatformAccount

log = logging.getLogger(__name__)

_MIN_AGE_HOURS = 48
_FORCE_EVAL_HOURS = 72   # passé ce délai → évaluation forcée même si critères non atteints
_MIN_HEALTH_SCORE = 70
_MAX_ERRORS_24H = 3
_QUOTA_STEP = 5
_QUOTA_MAX = 30
_QUOTA_MIN = 5

_TRUST_ORDER = {
    DatadomeTrustLevel.LOW: 0,
    DatadomeTrustLevel.MEDIUM: 1,
    DatadomeTrustLevel.HIGH: 2,
}


def _trust_ge_medium(level: str) -> bool:
    return _TRUST_ORDER.get(level, 0) >= _TRUST_ORDER[DatadomeTrustLevel.MEDIUM]


async def evaluate_warmup_batch() -> dict:
    """
    Évalue tous les comptes EN_CHAUFFE et met à jour leur statut si éligible.

    Returns dict avec clés "promoted", "kept", "slowed".
    """
    now = datetime.now(UTC)
    promoted = kept = slowed = 0

    async with get_db() as db:
        result = await db.execute(
            select(PlatformAccount).where(PlatformAccount.status == AccountStatus.EN_CHAUFFE)
        )
        accounts = result.scalars().all()

    for account in accounts:
        # Calcul de l'âge en tenant compte des datetimes naïves (server_default)
        created = account.date_creation
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        age_hours = (now - created).total_seconds() / 3600

        if age_hours < _MIN_AGE_HOURS:
            kept += 1
            continue

        can_promote = (
            _trust_ge_medium(account.datadome_trust_level)
            and account.score_sante >= _MIN_HEALTH_SCORE
            and account.erreurs_24h <= _MAX_ERRORS_24H
        )

        if can_promote:
            new_status = AccountStatus.ACTIF
            new_quota = min(account.quota_actuel + _QUOTA_STEP, _QUOTA_MAX)
            promoted += 1
            log.info(
                "Compte %s → ACTIF (âge=%.1fh trust=%s santé=%d)",
                account.id, age_hours, account.datadome_trust_level, account.score_sante,
            )
        elif age_hours >= _FORCE_EVAL_HOURS:
            new_status = AccountStatus.RALENTI
            new_quota = max(account.quota_actuel - _QUOTA_STEP, _QUOTA_MIN)
            slowed += 1
            log.warning(
                "Compte %s → RALENTI (âge=%.1fh trust=%s santé=%d erreurs=%d)",
                account.id, age_hours, account.datadome_trust_level,
                account.score_sante, account.erreurs_24h,
            )
        else:
            kept += 1
            continue

        async with get_db() as db:
            await db.execute(
                update(PlatformAccount)
                .where(PlatformAccount.id == account.id)
                .values(status=new_status, quota_actuel=new_quota, derniere_action=now)
            )

    log.info(
        "evaluate_warmup_batch terminé : promoted=%d kept=%d slowed=%d",
        promoted, kept, slowed,
    )
    return {"promoted": promoted, "kept": kept, "slowed": slowed}


async def update_account_health(account_id: str, success: bool) -> None:
    """
    Ajuste le score de santé d'un compte après une action.

    success=True  → +2 pts (cap 100)
    success=False → -10 pts, erreurs_24h++, dégradation de statut si seuils franchis
    """
    account_uuid = uuid.UUID(account_id)
    now = datetime.now(UTC)

    async with get_db() as db:
        result = await db.execute(
            select(PlatformAccount).where(PlatformAccount.id == account_uuid).limit(1)
        )
        account = result.scalar_one_or_none()
        if not account:
            return

        if success:
            new_score = min(account.score_sante + 2, 100)
            new_errors = account.erreurs_24h
            new_status = account.status
        else:
            new_score = max(account.score_sante - 10, 0)
            new_errors = account.erreurs_24h + 1

            if new_errors >= 10 or new_score <= 0:
                new_status = AccountStatus.BLOQUE
                log.warning(
                    "Compte %s → BLOQUÉ (score=%d erreurs=%d)",
                    account_uuid, new_score, new_errors,
                )
            elif new_errors >= 5 or new_score <= 30:
                new_status = AccountStatus.RALENTI
                log.warning(
                    "Compte %s → RALENTI (score=%d erreurs=%d)",
                    account_uuid, new_score, new_errors,
                )
            else:
                new_status = account.status

        await db.execute(
            update(PlatformAccount)
            .where(PlatformAccount.id == account_uuid)
            .values(
                score_sante=new_score,
                erreurs_24h=new_errors,
                status=new_status,
                derniere_action=now,
            )
        )
