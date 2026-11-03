"""Mijn SlimStroom voor Home Assistant.

Leest de klant-API van app.mijnslimstroom.nl (dezelfde als de app):
live energiestromen, dagtotalen, saldo, stroomprijs en het
batterijplan van de thuisbatterij.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InvalidAuth, MijnSlimstroomApi, MijnSlimstroomError
from .const import DOMAIN
from .coordinator import MijnSlimstroomCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return ok
