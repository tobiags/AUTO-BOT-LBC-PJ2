"""Tests analyzer API - exposition des champs enrichis."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_analyzer_results_expose_enriched_ai_fields(client):
    listing = SimpleNamespace(
        id="123e4567-e89b-12d3-a456-426614174000",
        url="https://www.leboncoin.fr/voitures/123",
        title="Renault Clio",
        make="Renault",
        model="Clio",
        year=2018,
        km=85000,
        price=7500,
        price_score=8.5,
        market_avg_price=8200,
        market_sample_size=12,
        reliability_score=84,
        ai_summary="Bonne opportunite.",
        known_issues=["Courroie a surveiller"],
        inspection_tips=["Verifier l'embrayage"],
        negotiation_tip="Utiliser l'entretien a venir comme levier.",
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [listing]))
    )
    ctx = AsyncMock()
    ctx.__aenter__.return_value = db
    ctx.__aexit__.return_value = False

    with patch("app.api.analyzer.get_db", return_value=ctx):
        resp = await client.get("/analyzer/results")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["reliability_score"] == 84
    assert data[0]["known_issues"] == ["Courroie a surveiller"]
    assert data[0]["inspection_tips"] == ["Verifier l'embrayage"]
    assert data[0]["negotiation_tip"] == "Utiliser l'entretien a venir comme levier."
