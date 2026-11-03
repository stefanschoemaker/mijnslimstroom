"""Draaibeurten terugmelden: per slim apparaat kijkt de tracker naar de
entiteiten uit de opties (loopt-entiteit en/of energie-entiteit), meldt
de start aan de app en bij het einde de gemeten kWh. Zonder opties
doet hij niets."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event

from .api import MijnSlimstroomApi, MijnSlimstroomError
from .const import (
    DEFAULT_THRESHOLD_W,
    MIN_RUN_SECONDS,
    OPT_ENERGY_ENTITY,
    OPT_LOADS,
    OPT_RUNNING_ENTITY,
    OPT_THRESHOLD_W,
)

_LOGGER = logging.getLogger(__name__)

# Toestanden die "staat uit" betekenen voor een loopt-entiteit; alles
# anders (on, run, running, wash, drying, heating, ...) telt als draaien.
OFF_STATES = {
    "off", "unavailable", "unknown", "none", "", "idle", "stop", "stopped",
    "standby", "end", "finish", "finished", "pause", "paused", "ready",
    "false", "0", "0.0",
}


def _float(state: State | None) -> float | None:
    if state is None or state.state in ("unavailable", "unknown", ""):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _is_kwh(state: State | None) -> bool:
    unit = str((state.attributes.get("unit_of_measurement") if state else "") or "").lower()
    return unit in ("kwh", "wh", "mwh")


def _kwh(state: State | None) -> float | None:
    v = _float(state)
    if v is None:
        return None
    unit = str(state.attributes.get("unit_of_measurement") or "").lower()
    return v / 1000.0 if unit == "wh" else v * 1000.0 if unit == "mwh" else v


@dataclass
class _Run:
    started_at: int
    kwh_start: float | None = None      # kWh-teller bij de start
    wh_acc: float = 0.0                 # geïntegreerd vermogen (W-sensor)
    last_w: float | None = None
    last_t: float = field(default_factory=time.time)
    started_reported: bool = False


class RunTracker:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: MijnSlimstroomApi) -> None:
        self._hass = hass
        self._entry = entry
        self._api = api
        self._runs: dict[str, _Run] = {}
        self._unsub: list = []

    @property
    def loads(self) -> dict[str, dict]:
        return dict((self._entry.options or {}).get(OPT_LOADS) or {})

    async def async_start(self) -> None:
        for load_id, opt in self.loads.items():
            ents = [e for e in (opt.get(OPT_RUNNING_ENTITY), opt.get(OPT_ENERGY_ENTITY)) if e]
            if not ents:
                continue
            self._unsub.append(async_track_state_change_event(
                self._hass, ents, self._make_handler(load_id)))
            _LOGGER.debug("tracker voor %s op %s", load_id, ents)
            # Al bezig bij het opstarten? Dan nu de start vastleggen.
            await self._evaluate(load_id)

    @callback
    def async_stop(self) -> None:
        for u in self._unsub:
            u()
        self._unsub.clear()

    def _make_handler(self, load_id: str):
        async def _handle(event: Event) -> None:
            await self._evaluate(load_id)
        return _handle

    def _running(self, load_id: str) -> bool | None:
        """True/False, of None als geen van beide entiteiten uitsluitsel geeft."""
        opt = self.loads.get(load_id) or {}
        st = self._hass.states.get(opt.get(OPT_RUNNING_ENTITY) or "")
        if st is not None and st.state not in ("unavailable", "unknown"):
            return st.state.lower() not in OFF_STATES
        es = self._hass.states.get(opt.get(OPT_ENERGY_ENTITY) or "")
        if es is not None and not _is_kwh(es):
            w = _float(es)
            if w is not None:
                return w > float(opt.get(OPT_THRESHOLD_W) or DEFAULT_THRESHOLD_W)
        return None

    def _integrate(self, load_id: str, run: _Run) -> None:
        opt = self.loads.get(load_id) or {}
        es = self._hass.states.get(opt.get(OPT_ENERGY_ENTITY) or "")
        if es is None or _is_kwh(es):
            return
        w = _float(es)
        now = time.time()
        if run.last_w is not None:
            run.wh_acc += (run.last_w + (w if w is not None else run.last_w)) / 2.0 * (now - run.last_t) / 3600.0
        run.last_w = w if w is not None else run.last_w
        run.last_t = now

    def _measured_kwh(self, load_id: str, run: _Run) -> float | None:
        opt = self.loads.get(load_id) or {}
        es = self._hass.states.get(opt.get(OPT_ENERGY_ENTITY) or "")
        if es is None:
            return None
        if _is_kwh(es):
            end = _kwh(es)
            if end is None or run.kwh_start is None or end < run.kwh_start:
                return None
            return round(end - run.kwh_start, 3)
        self._integrate(load_id, run)
        return round(run.wh_acc / 1000.0, 3)

    async def _evaluate(self, load_id: str) -> None:
        running = self._running(load_id)
        run = self._runs.get(load_id)
        if running and run is None:
            opt = self.loads.get(load_id) or {}
            es = self._hass.states.get(opt.get(OPT_ENERGY_ENTITY) or "")
            run = _Run(started_at=int(time.time()), kwh_start=_kwh(es) if _is_kwh(es) else None,
                       last_w=_float(es) if es is not None and not _is_kwh(es) else None)
            self._runs[load_id] = run
            await self._report(load_id, run.started_at, None, None)
            run.started_reported = True
            return
        if run is None:
            return
        if running:
            self._integrate(load_id, run)
            return
        if running is None:
            return
        # einde van de draaibeurt
        del self._runs[load_id]
        ended = int(time.time())
        if ended - run.started_at < MIN_RUN_SECONDS:
            _LOGGER.debug("%s: draaibeurt van %d s genegeerd", load_id, ended - run.started_at)
            return
        await self._report(load_id, run.started_at, ended, self._measured_kwh(load_id, run))

    async def _report(self, load_id: str, started_at: int, ended_at: int | None, kwh: float | None) -> None:
        try:
            await self._api.report_run(load_id, started_at, ended_at, kwh)
        except MijnSlimstroomError as e:
            _LOGGER.warning("draaibeurt van %s niet gemeld: %s", load_id, e)
