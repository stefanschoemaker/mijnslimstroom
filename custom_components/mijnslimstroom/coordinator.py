"""Coordinator: een poll-lus voor alle Mijn SlimStroom-sensoren.

Live-vermogens elke minuut; dagtotalen, saldo, prijs en batterijplan
om de vijf minuten (die bewegen niet sneller). Een trage-blok-fout is
niet fataal: de live-data blijft dan gewoon verversen en de trage
sensoren houden hun laatste waarde.
"""

from __future__ import annotations

import logging
from datetime import timedelta, datetime, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import InvalidAuth, MijnSlimstroomApi, MijnSlimstroomError
from .const import DOMAIN, SLOW_EVERY_N_TICKS, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class MijnSlimstroomCoordinator(DataUpdateCoordinator[dict]):
    """Haalt live + (periodiek) de trage blokken op."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, api: MijnSlimstroomApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.api = api
        self._tick = 0
        self._slow: dict[str, Any] = {}

    async def _async_update_data(self) -> dict:
        try:
            live = await self.api.live()
        except InvalidAuth as e:
            raise ConfigEntryAuthFailed from e
        except MijnSlimstroomError as e:
            raise UpdateFailed(str(e)) from e

        if self._tick % SLOW_EVERY_N_TICKS == 0 or not self._slow:
            await self._refresh_slow()
        self._tick += 1

        return {"live": live, **self._slow}

    async def _refresh_slow(self) -> None:
        for key, fetch in (
            ("today", self.api.today),
            ("earnings", self.api.earnings_today),
            ("pricing", self.api.pricing_today),
            ("forecast", self.api.forecast),
        ):
            try:
                self._slow[key] = await fetch()
            except InvalidAuth:
                raise
            except MijnSlimstroomError as e:
                # Niet fataal: saldo/prijs/plan kunnen een blok missen
                # (site zonder contract, plan nog niet beschikbaar).
                _LOGGER.debug("traag blok %s niet ververst: %s", key, e)

    # ---- afgeleiden voor de sensoren ---------------------------------

    def current_price_eur_per_kwh(self) -> float | None:
        p = self._slow.get("pricing")
        if not p:
            return None
        idx = p.get("current_hour_idx")
        prices = p.get("prices_eur_per_kwh") or []
        if idx is None or idx >= len(prices):
            return None
        return prices[idx]

    def current_plan_action(self) -> str | None:
        f = self._slow.get("forecast")
        if not f or not f.get("available"):
            return None
        now = datetime.now(timezone.utc)
        for s in f.get("slots") or []:
            try:
                start = datetime.fromisoformat(str(s["start"]).replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if start <= now < start + timedelta(seconds=s.get("duration_sec", 900)):
                return s.get("action")
        return None
