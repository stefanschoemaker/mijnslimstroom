"""Mijn SlimStroom voor Home Assistant.

Leest de klant-API van app.mijnslimstroom.nl (dezelfde als de app):
live energiestromen, dagtotalen, saldo, stroomprijs en het
batterijplan van de thuisbatterij.
"""

from __future__ import annotations

import logging
from datetime import datetime

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InvalidAuth, MijnSlimstroomApi, MijnSlimstroomError
from .const import DOMAIN, SERVICE_REPORT_RUN
from .coordinator import MijnSlimstroomCoordinator
from .tracker import RunTracker

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

SERVICE_SCHEMA = vol.Schema({
    vol.Required("load_id"): cv.string,
    vol.Required("started_at"): cv.datetime,
    vol.Optional("ended_at"): cv.datetime,
    vol.Optional("kwh"): vol.All(vol.Coerce(float), vol.Range(min=0, max=200)),
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = MijnSlimstroomApi(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    try:
        await api.login()
    except InvalidAuth as e:
        raise ConfigEntryAuthFailed from e
    except MijnSlimstroomError as e:
        raise ConfigEntryNotReady from e

    coordinator = MijnSlimstroomCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Draaibeurten terugmelden (opties) + de service voor eigen
    # automatiseringen. Opties gewijzigd = entry herladen.
    tracker = RunTracker(hass, entry, api)
    await tracker.async_start()
    entry.async_on_unload(tracker.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _report(call: ServiceCall) -> None:
        def _ts(v: datetime | None) -> int | None:
            return int(v.timestamp()) if v is not None else None
        try:
            await api.report_run(call.data["load_id"], _ts(call.data["started_at"]),
                                 _ts(call.data.get("ended_at")), call.data.get("kwh"), source="manual")
        except MijnSlimstroomError as e:
            raise HomeAssistantError(f"draaibeurt niet gemeld: {e}") from e
        await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_REPORT_RUN):
        hass.services.async_register(DOMAIN, SERVICE_REPORT_RUN, _report, schema=SERVICE_SCHEMA)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return ok
