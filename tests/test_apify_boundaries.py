from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import boundaries


async def _async_items(items):
    for item in items:
        yield item


def _client(monkeypatch):
    client = MagicMock()
    client.close = AsyncMock()
    monkeypatch.setattr(boundaries, "_apify_client", lambda token: client)
    return client


@pytest.mark.asyncio
async def test_apify_validate_token_returns_plain_identity(monkeypatch):
    client = _client(monkeypatch)
    user = AsyncMock()
    user.get.return_value = {"id": "user-1", "username": "owner"}
    client.user.return_value = user

    result = await boundaries.apify_validate_token("secret")

    assert result == {"id": "user-1", "username": "owner"}
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_apify_lists_actors_and_tasks_as_plain_dicts(monkeypatch):
    client = _client(monkeypatch)
    actors = AsyncMock()
    actors.list.return_value = SimpleNamespace(items=[{"id": "actor-1"}])
    tasks = AsyncMock()
    tasks.list.return_value = SimpleNamespace(items=[{"id": "task-1"}])
    client.actors.return_value = actors
    client.tasks.return_value = tasks

    assert await boundaries.apify_list_actors("secret") == [{"id": "actor-1"}]
    assert await boundaries.apify_list_tasks("secret") == [{"id": "task-1"}]


@pytest.mark.asyncio
async def test_apify_start_resource_uses_actor_or_task(monkeypatch):
    actor = AsyncMock()
    actor.start.return_value = {"id": "run-1", "status": "READY"}
    client = _client(monkeypatch)
    client.actor.return_value = actor

    run = await boundaries.apify_start_resource(
        "secret", "actor", "owner/demo", {"limit": 10}
    )

    assert run["id"] == "run-1"
    actor.start.assert_awaited_once_with(run_input={"limit": 10})

    task = AsyncMock()
    task.start.return_value = {"id": "run-2", "status": "READY"}
    client.task.return_value = task
    run = await boundaries.apify_start_resource(
        "secret", "task", "task-1", {"limit": 5}
    )
    assert run["id"] == "run-2"
    task.start.assert_awaited_once_with(task_input={"limit": 5})


@pytest.mark.asyncio
async def test_apify_start_resource_rejects_unknown_type(monkeypatch):
    client = _client(monkeypatch)

    with pytest.raises(ValueError, match="resource_type"):
        await boundaries.apify_start_resource("secret", "schedule", "id", {})

    client.actor.assert_not_called()
    client.task.assert_not_called()


@pytest.mark.asyncio
async def test_apify_iter_dataset_preserves_indexes(monkeypatch):
    dataset = MagicMock()
    dataset.iterate_items.return_value = _async_items([{"phone": "0612345678"}])
    client = _client(monkeypatch)
    client.dataset.return_value = dataset

    rows = [row async for row in boundaries.apify_iter_dataset("secret", "ds-1")]
    assert rows == [(0, {"phone": "0612345678"})]
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_apify_get_and_list_recent_runs(monkeypatch):
    client = _client(monkeypatch)
    run = AsyncMock()
    run.get.return_value = {"id": "run-1", "status": "SUCCEEDED"}
    runs = AsyncMock()
    runs.list.return_value = SimpleNamespace(items=[{"id": "run-1"}])
    client.run.return_value = run
    client.runs.return_value = runs

    assert await boundaries.apify_get_run("secret", "run-1") == {
        "id": "run-1",
        "status": "SUCCEEDED",
    }
    assert await boundaries.apify_list_recent_runs("secret", limit=25) == [
        {"id": "run-1"}
    ]
    runs.list.assert_awaited_once_with(limit=25, desc=True)


@pytest.mark.asyncio
async def test_apify_create_and_delete_webhook(monkeypatch):
    client = _client(monkeypatch)
    webhooks = AsyncMock()
    webhooks.create.return_value = {"id": "webhook-1"}
    webhook = AsyncMock()
    client.webhooks.return_value = webhooks
    client.webhook.return_value = webhook

    result = await boundaries.apify_create_webhook(
        "secret",
        "actor",
        "owner/demo",
        "https://example.test/webhooks/apify",
        "webhook-secret",
    )
    await boundaries.apify_delete_webhook("secret", "webhook-1")

    assert result == {"id": "webhook-1"}
    call = webhooks.create.await_args.kwargs
    assert call["actor_id"] == "owner/demo"
    assert call["actor_task_id"] is None
    assert "ACTOR.RUN.SUCCEEDED" in call["event_types"]
    assert "webhook-secret" in call["headers_template"]
    webhook.delete.assert_awaited_once_with()
