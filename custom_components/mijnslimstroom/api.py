"""Kleine async-client voor de Mijn SlimStroom klant-API.

Zelfde API als de app op app.mijnslimstroom.nl: JWT via
/api/auth/login (7 dagen geldig), site-scope zit IN het token - er
gaat nooit een site-parameter over de lijn. Bij een 401 logt de
client een keer opnieuw in en herhaalt het verzoek; blijft het 401,
dan zijn de inloggegevens ingetrokken en hoort Home Assistant een
herauthenticatie te starten.
"""

from __future__ import annotations

import time
from typing import Any

import aiohttp

from .const import BASE_URL


class MijnSlimstroomError(Exception):
    """API onbereikbaar of onverwacht antwoord."""


class InvalidAuth(MijnSlimstroomError):
    """Inloggegevens geweigerd."""


class MijnSlimstroomApi:
    """Session-injected client (Home Assistant beheert de aiohttp-sessie)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        base_url: str = BASE_URL,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._token: str | None = None
        self._token_expires: float = 0.0
        self.site_id: str | None = None
        self.display_name: str | None = None

    async def login(self) -> None:
        try:
            async with self._session.post(
                f"{self._base_url}/api/auth/login",
                json={"username": self._username, "password": self._password},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                if r.status == 401:
                    raise InvalidAuth("inloggegevens geweigerd")
                r.raise_for_status()
                body = await r.json()
        except InvalidAuth:
            raise
        except Exception as e:  # noqa: BLE001 - netwerk/parse -> een fouttype
            raise MijnSlimstroomError(
                f"login mislukt: {type(e).__name__}: {e}"
            ) from e
        self._token = body["access_token"]
        # Ruime marge voor de verversing: een verzoek vlak voor expiry
        # mag nooit met een net-verlopen token vertrekken.
        self._token_expires = time.monotonic() + body.get("expires_in", 3600) - 300
        self.site_id = body.get("site_id")
        self.display_name = body.get("display_name")

    async def _get(self, path: str, *, _retried: bool = False) -> Any:
        if self._token is None or time.monotonic() >= self._token_expires:
            await self.login()
        try:
            async with self._session.get(
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                if r.status == 401:
                    if _retried:
                        raise InvalidAuth("token en herlogin geweigerd")
                    # Token ingetrokken voor de expiry (wachtwoord
                    # gewijzigd, site verhuisd): een verse login proberen.
                    self._token = None
                    return await self._get(path, _retried=True)
                r.raise_for_status()
                return await r.json()
        except (InvalidAuth, MijnSlimstroomError):
            raise
        except Exception as e:  # noqa: BLE001
            raise MijnSlimstroomError(
                f"GET {path} mislukt: {type(e).__name__}: {e}"
            ) from e

    async def _post(self, path: str, body: dict, *, _retried: bool = False) -> Any:
        if self._token is None or time.monotonic() >= self._token_expires:
            await self.login()
        try:
            async with self._session.post(
                f"{self._base_url}{path}",
                json=body,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                if r.status == 401:
                    if _retried:
                        raise InvalidAuth("token en herlogin geweigerd")
                    self._token = None
                    return await self._post(path, body, _retried=True)
                if r.status >= 400:
                    detail = (await r.text())[:200]
                    raise MijnSlimstroomError(f"POST {path}: {r.status} {detail}")
                return await r.json()
        except (InvalidAuth, MijnSlimstroomError):
            raise
        except Exception as e:  # noqa: BLE001
            raise MijnSlimstroomError(
                f"POST {path} mislukt: {type(e).__name__}: {e}"
            ) from e

    async def live(self) -> dict:
        return await self._get("/api/live")

    async def today(self) -> dict:
        return await self._get("/api/today")

    async def earnings_today(self) -> dict:
        return await self._get("/api/earnings?range=today")

    async def pricing_today(self) -> dict:
        return await self._get("/api/pricing/today?resolution=15min")

    async def pricing_config(self) -> dict:
        return await self._get("/api/pricing/config")

    async def forecast(self) -> dict:
        return await self._get("/api/forecast")

    async def smart(self) -> dict:
        """Slimme momenten: {"enabled": false} zolang de klant ze niet
        aanzet in de app (Account > Slimme apparaten)."""
        return await self._get("/api/smart")

    async def report_run(self, load_id: str, started_at: int, ended_at: int | None,
                         kwh: float | None, source: str = "ha") -> dict:
        """Een draaibeurt melden: bij de start (ended_at None) en nog
        eens bij het einde met de meting; de server voegt ze samen."""
        return await self._post("/api/smart/runs", {
            "load_id": load_id, "started_at": int(started_at),
            "ended_at": int(ended_at) if ended_at is not None else None,
            "kwh": round(float(kwh), 3) if kwh is not None else None,
            "source": source,
        })
