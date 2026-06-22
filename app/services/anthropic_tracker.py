"""
Suivi du coût Anthropic estimé via les tokens de chaque appel.
Mise à jour en DB asynchrone et non-bloquante.

Tarifs claude-sonnet-4-6 (en vigueur juin 2026, $/M tokens) :
  input  : $3.00 / M tokens
  output : $15.00 / M tokens
"""
import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert

log = logging.getLogger(__name__)

# Tarifs Sonnet 4.6 en USD / token
_IN_PRICE = 3.00 / 1_000_000
_OUT_PRICE = 15.00 / 1_000_000
_LOW_THRESHOLD = 5.0  # USD

# Accumulateur en mémoire (thread-safe via asyncio)
_total_cost_usd: float = 0.0


async def track_usage(input_tokens: int, output_tokens: int) -> None:
    """Appeler après chaque réponse Anthropic — met à jour la DB."""
    global _total_cost_usd
    cost = input_tokens * _IN_PRICE + output_tokens * _OUT_PRICE
    _total_cost_usd += cost

    # Import local pour éviter les imports circulaires
    try:
        from app.db import get_db
        from app.tables import ServiceBalance

        async with get_db() as db:
            await db.execute(
                pg_insert(ServiceBalance)
                .values(
                    service="anthropic",
                    label="Anthropic Claude",
                    balance=round(_total_cost_usd, 4),
                    currency="USD",
                    is_low=_total_cost_usd > _LOW_THRESHOLD,
                    low_threshold=_LOW_THRESHOLD,
                    last_updated=datetime.now(UTC),
                )
                .on_conflict_do_update(
                    index_elements=["service"],
                    set_={
                        "balance": round(_total_cost_usd, 4),
                        "is_low": _total_cost_usd > _LOW_THRESHOLD,
                        "last_updated": datetime.now(UTC),
                    },
                )
            )
            await db.commit()
    except Exception as exc:
        log.debug("anthropic_tracker DB update failed: %s", exc)
