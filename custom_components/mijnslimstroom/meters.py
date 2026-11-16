"""Meters terugmelden: elke vijf minuten de stand van de gekoppelde
kWh-tellers (warmtepomp, laadpaal, zonnepanelen die de installatie
niet zelf meet) naar de app. Zonder opties doet hij niets."""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .api import MijnSlimstroomApi, MijnSlimstroomError
from .const import METER_INTERVAL_SECONDS, METER_REPEAT_SECONDS, METERS, OPT_METERS
from .tracker import _is_kwh, _kwh

_LOGGER = logging.getLogger(__name__)


class MeterReporter:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: MijnSlimstroomApi) -> None:
        self._hass = hass
        self._entry = entry
        self._api = api
        self._sent: dict[str, tuple[float, float]] = {}
        self._unsub = None

    @property
    def meters(self) -> dict[str, str]:
        opts = (self._entry.options or {}).get(OPT_METERS) or {}
        return {m: e for m, e in opts.items() if m in METERS and e}

    async def async_start(self) -> None:
        if not self.meters:
            return
        self._unsub = async_track_time_interval(
            self._hass, self._tick, timedelta(seconds=METER_INTERVAL_SECONDS))
        await self._tick(None)

    @callback
    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def _readings(self, now: float) -> list[dict]:
        out = []
        for meter, entity_id in self.meters.items():
            state = self._hass.states.get(entity_id)
            if not _is_kwh(state):
                continue
            kwh = _kwh(state)
            if kwh is None or kwh < 0:
                continue
            last = self._sent.get(meter)
            if last and last[0] == kwh and now - last[1] < METER_REPEAT_SECONDS:
                continue
            out.append({"meter": meter, "kwh": round(kwh, 3), "at": int(now)})
        return out

    async def _tick(self, _now) -> None:
        now = time.time()
        readings = self._readings(now)
        if not readings:
            return
        try:
            await self._api.report_meters(readings)
        except MijnSlimstroomError as e:
            _LOGGER.warning("meterstanden niet gemeld: %s", e)
            return
        for r in readings:
            self._sent[r["meter"]] = (r["kwh"], now)
