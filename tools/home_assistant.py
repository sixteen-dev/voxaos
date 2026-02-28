import os
from datetime import datetime, timedelta

import httpx

from core.config import HomeAssistantConfig


class HomeAssistantTools:
    def __init__(self, config: HomeAssistantConfig):
        self.config = config
        self.base_url = config.url
        token = os.environ.get(config.token_env, "")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def ha_get_states(self, domain: str | None = None) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/api/states", headers=self.headers)
            resp.raise_for_status()
            states = resp.json()
            if domain:
                states = [s for s in states if s["entity_id"].startswith(f"{domain}.")]
            lines = [f"{s['entity_id']}: {s['state']}" for s in states]
            return "\n".join(lines) or "No entities found."

    async def ha_get_state(self, entity_id: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/api/states/{entity_id}", headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            attrs = ", ".join(f"{k}={v}" for k, v in data.get("attributes", {}).items())
            return f"{entity_id}: {data['state']} ({attrs})"

    async def ha_set_state(self, entity_id: str, state: str, attributes: dict | None = None) -> str:
        payload: dict = {"state": state}
        if attributes:
            payload["attributes"] = attributes
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/states/{entity_id}",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return f"Set {entity_id} to {state}"

    async def ha_call_service(self, domain: str, service: str, entity_id: str, data: dict | None = None) -> str:
        payload = {"entity_id": entity_id, **(data or {})}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/services/{domain}/{service}",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return f"Called {domain}.{service} on {entity_id}"

    async def ha_get_history(self, entity_id: str, hours: int = 24) -> str:
        start = (datetime.now() - timedelta(hours=hours)).isoformat()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/history/period/{start}",
                params={"filter_entity_id": entity_id},
                headers=self.headers,
            )
            resp.raise_for_status()
            history = resp.json()
            if not history or not history[0]:
                return "No history found."
            entries = history[0]
            lines = [f"{e['last_changed']}: {e['state']}" for e in entries[-20:]]
            return "\n".join(lines)
