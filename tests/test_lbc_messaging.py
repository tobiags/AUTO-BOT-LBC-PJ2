def test_extract_french_phone_numbers_normalizes_e164():
    from app.services.lbc_messaging import extract_phone_numbers

    assert extract_phone_numbers("Appelez-moi au 06 12 34 56 78 demain") == [
        "+33612345678"
    ]


def test_message_key_is_stable_across_retries():
    from app.services.lbc_messaging import outbound_message_key

    first = outbound_message_key("campaign-1", "listing-1")
    second = outbound_message_key("campaign-1", "listing-1")

    assert first == second
    assert first.startswith("outbound:")


def test_vehicle_criteria_validate_budget_and_keep_search_terms():
    from app.models import VehicleSearchCriteria

    criteria = VehicleSearchCriteria(
        brand_model="Renault Clio",
        vehicle_type="Citadine",
        region="75",
        budget_min=3000,
        budget_max=9000,
    )

    assert criteria.model_dump(exclude_none=True) == {
        "brand_model": "Renault Clio",
        "vehicle_type": "Citadine",
        "region": "75",
        "budget_min": 3000,
        "budget_max": 9000,
    }


def test_vehicle_criteria_reject_inverted_budget():
    import pytest

    from app.models import VehicleSearchCriteria

    with pytest.raises(ValueError, match="budget_min"):
        VehicleSearchCriteria(budget_min=9000, budget_max=3000)


def test_worker_marks_campaign_failed_when_async_execution_raises(monkeypatch):
    from app import tasks

    calls = []

    def fake_run(coro):
        coro.close()
        if not calls:
            calls.append("run")
            raise RuntimeError("different loop")
        calls.append("mark")
        return None

    monkeypatch.setattr(tasks, "_run", fake_run)

    with __import__("pytest").raises(RuntimeError, match="different loop"):
        tasks.run_lbc_message_campaign_task(
            "a0c62cf6-655e-4fc3-a6c6-8ff584721baa",
            "9ffe13d8-46bf-433f-9d5e-4b3eeb4fa989",
        )

    assert calls == ["run", "mark"]
