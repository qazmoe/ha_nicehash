"""NiceHash API v2 client for the nicehash_api integration."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import httpx
from hashlib import sha256
import hmac

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://api2.nicehash.com"


class NiceHashApiError(Exception):
    """Raised when the NiceHash API returns an error."""


class NiceHashClient:
    """Async client for the NiceHash v2 REST API (HMAC request signing)."""

    def __init__(self, api_key: str, api_secret: str, org_id: str) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._org_id = org_id
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=API_BASE, timeout=30)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, params: dict[str, str] | None = None, auth: bool = True) -> Any:
        client = await self._ensure_client()

        query = ""
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())

        headers = {"Content-Type": "application/json"}
        if auth:
            xtime = str(int(time.time() * 1000))
            xnonce = str(uuid.uuid4())

            # NiceHash HMAC signing: key\0time\0nonce\0\0org\0\0method\0path\0query
            message = (
                f"{self._api_key}\00{xtime}\00{xnonce}\00\00{self._org_id}"
                f"\00\00{method}\00{path}\00{query}"
            )
            digest = hmac.new(
                self._api_secret.encode(), message.encode(), sha256
            ).hexdigest()

            headers.update({
                "X-Time": xtime,
                "X-Nonce": xnonce,
                "X-Auth": f"{self._api_key}:{digest}",
                "X-Organization-Id": self._org_id,
                "X-Request-Id": str(uuid.uuid4()),
            })

        try:
            resp = await client.request(
                method, path, headers=headers, params=params or None
            )
        except httpx.HTTPError as err:
            raise NiceHashApiError(f"Connection error talking to NiceHash: {err}") from err

        if resp.status_code == 200:
            return resp.json()
        # NiceHash errors carry a JSON body with messages
        try:
            body = resp.json()
            msg = body.get("messages") or body.get("message") or str(body)[:200]
        except Exception:
            msg = resp.text[:200]
        raise NiceHashApiError(f"NiceHash API error {resp.status_code}: {msg}")

    async def validate_credentials(self) -> dict[str, Any]:
        """Cheap authenticated call to verify key/secret/org during config flow."""
        return await self._request("GET", "/main/api/v2/accounting/accounts2", {" fiat": "USD"})

    # -- Public (unauthenticated) market endpoints -------------------------

    async def get_simplemultialgo(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/main/api/v2/public/simplemultialgo/info", auth=False)
        return data.get("miningAlgorithms", [])

    async def get_global_stats_current(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/main/api/v2/public/stats/global/current", auth=False)
        return data.get("algos", [])

    async def get_global_stats_24h(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/main/api/v2/public/stats/global/24h", auth=False)
        return data.get("algos", [])

    async def get_algo_history(self, algorithm: str) -> list[list[float]]:
        data = await self._request(
            "GET",
            "/main/api/v2/public/algo/history",
            {"algorithm": algorithm},
            auth=False,
        )
        return data if isinstance(data, list) else []

    async def get_mining_algorithms(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/main/api/v2/mining/algorithms", auth=False)
        return data.get("miningAlgorithms", [])

    # -- Data endpoints -------------------------------------------------

    async def get_accounts(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/main/api/v2/accounting/accounts2")
        return data.get("accounts", []) if isinstance(data, dict) else []

    async def get_rigs(self) -> dict[str, Any]:
        return await self._request("GET", "/main/api/v2/mining/rigs2", {"size": "500"})

    async def get_payouts(self, size: int = 84) -> dict[str, Any]:
        return await self._request(
            "GET", "/main/api/v2/mining/rigs/payouts", {"size": str(size)}
        )
