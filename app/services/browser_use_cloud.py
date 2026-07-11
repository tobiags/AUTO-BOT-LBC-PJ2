from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class BrowserUseTemplate:
    label: str
    prompt: str
    allowed_domains: tuple[str, ...]


BROWSER_USE_TEMPLATES = {
    "listing_diagnostic": BrowserUseTemplate(
        label="Diagnostic annonce",
        prompt=(
            "Ouvre l'URL d'annonce fournie et retourne son etat, "
            "son titre et les blocages visibles."
        ),
        allowed_domains=("leboncoin.fr", "www.leboncoin.fr"),
    ),
    "listing_enrichment": BrowserUseTemplate(
        label="Enrichissement annonce",
        prompt=(
            "Analyse l'annonce fournie et retourne les criteres "
            "techniques explicitement visibles."
        ),
        allowed_domains=("leboncoin.fr", "www.leboncoin.fr"),
    ),
    "messaging_assist": BrowserUseTemplate(
        label="Assistance messagerie",
        prompt="Ouvre la conversation indiquee et prepare le message sans l'envoyer.",
        allowed_domains=("leboncoin.fr", "www.leboncoin.fr"),
    ),
    "account_diagnostic": BrowserUseTemplate(
        label="Diagnostic compte",
        prompt=(
            "Controle l'etat de la session du compte et retourne "
            "les actions requises sans modification."
        ),
        allowed_domains=("leboncoin.fr", "www.leboncoin.fr"),
    ),
}


class BrowserUseCloudClient:
    def __init__(self, api_key: str, *, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = "https://api.browser-use.com/api/v2"

    async def create_task(
        self,
        *,
        task: str,
        metadata: dict[str, str] | None = None,
        allowed_domains: tuple[str, ...] = (),
        session_id: str | None = None,
        session_settings: dict[str, Any] | None = None,
        structured_output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"task": task}
        if metadata:
            payload["metadata"] = metadata
        if allowed_domains:
            payload["allowedDomains"] = list(allowed_domains)
        if session_id:
            payload["sessionId"] = session_id
        if session_settings:
            payload["sessionSettings"] = session_settings
        if structured_output:
            payload["structuredOutput"] = structured_output
        return await self._request("POST", "/tasks", json=payload)

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/tasks/{task_id}/status")

    async def get_task(self, task_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/tasks/{task_id}")

    async def stop_task(self, task_id: str, *, stop_session: bool = True) -> dict[str, Any]:
        action = "stop_task_and_session" if stop_session else "stop"
        return await self._request("PATCH", f"/tasks/{task_id}", json={"action": action})

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        headers = {"X-Browser-Use-API-Key": self.api_key}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                **kwargs,
            )
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"Browser Use returned HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
        return response.json()
