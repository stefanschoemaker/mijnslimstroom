"""Config flow: inloggen met de app-gegevens van Mijn SlimStroom."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import InvalidAuth, MijnSlimstroomApi, MijnSlimstroomError
from .const import (
    CONF_DISPLAY_NAME,
    CONF_SITE_ID,
    DEFAULT_THRESHOLD_W,
    DOMAIN,
    OPT_ENERGY_ENTITY,
    OPT_LOADS,
    OPT_RUNNING_ENTITY,
    OPT_THRESHOLD_W,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class MijnSlimstroomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gebruikersnaam + wachtwoord, geverifieerd tegen de echte API."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MijnSlimstroomOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api = MijnSlimstroomApi(
                async_get_clientsession(self.hass),
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await api.login()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except MijnSlimstroomError as e:
                # De onderliggende oorzaak (DNS, timeout, TLS, 5xx)
                # verdwijnt anders achter een generiek "kan niet
                # bereiken" - een blik in het log moet genoeg zijn.
                _LOGGER.warning("Verbinden mislukt: %s", e)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_USERNAME]}:{api.site_id}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=api.display_name or api.site_id or user_input[CONF_USERNAME],
                    data={
                        **user_input,
                        CONF_SITE_ID: api.site_id,
                        CONF_DISPLAY_NAME: api.display_name,
                    },
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api = MijnSlimstroomApi(
                async_get_clientsession(self.hass),
                entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await api.login()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except MijnSlimstroomError as e:
                _LOGGER.warning("Verbinden mislukt: %s", e)
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )


class MijnSlimstroomOptionsFlow(OptionsFlow):
    """Per slim apparaat (uit de app) de entiteiten kiezen waarmee de
    integratie draaibeurten terugmeldt: een loopt-entiteit en/of een
    energie-entiteit (kWh-teller of W-vermogen). Stap 1 kiest het
    apparaat, stap 2 de entiteiten; "Klaar" slaat alles op."""

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}
        self._load_id: str | None = None

    def _loads(self) -> list[dict]:
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None or not coordinator.smart_enabled():
            return []
        return list(coordinator.smart().get("loads") or [])

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._options:
            self._options = {OPT_LOADS: dict((self.config_entry.options or {}).get(OPT_LOADS) or {})}
        loads = self._loads()
        if not loads:
            return self.async_abort(reason="no_smart_loads")
        if user_input is not None:
            if user_input["load"] == "_done":
                return self.async_create_entry(title="", data=self._options)
            self._load_id = user_input["load"]
            return await self.async_step_load()
        cfg = self._options[OPT_LOADS]
        options = [
            SelectOptionDict(
                value=str(l["id"]),
                label=f"{l.get('name') or l['id']}" + (" (gekoppeld)" if cfg.get(str(l["id"])) else ""),
            )
            for l in loads
        ] + [SelectOptionDict(value="_done", label="Klaar")]
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("load"): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)),
            }),
        )

    async def async_step_load(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._load_id is not None
        load = next((l for l in self._loads() if str(l["id"]) == self._load_id), {})
        current = dict(self._options[OPT_LOADS].get(self._load_id) or {})
        errors: dict[str, str] = {}
        if user_input is not None:
            running = user_input.get(OPT_RUNNING_ENTITY)
            energy = user_input.get(OPT_ENERGY_ENTITY)
            if not running and not energy:
                self._options[OPT_LOADS].pop(self._load_id, None)
                return await self.async_step_init()
            if not running:
                st = self.hass.states.get(energy)
                unit = str((st.attributes.get("unit_of_measurement") if st else "") or "").lower()
                if unit in ("kwh", "wh", "mwh"):
                    errors["base"] = "kwh_needs_running"
            if not errors:
                self._options[OPT_LOADS][self._load_id] = {
                    OPT_RUNNING_ENTITY: running or None,
                    OPT_ENERGY_ENTITY: energy or None,
                    OPT_THRESHOLD_W: int(user_input.get(OPT_THRESHOLD_W) or DEFAULT_THRESHOLD_W),
                }
                return await self.async_step_init()
            current = user_input
        schema = vol.Schema({
            vol.Optional(OPT_RUNNING_ENTITY, description={"suggested_value": current.get(OPT_RUNNING_ENTITY)}):
                EntitySelector(EntitySelectorConfig(domain=["binary_sensor", "switch", "sensor", "input_boolean"])),
            vol.Optional(OPT_ENERGY_ENTITY, description={"suggested_value": current.get(OPT_ENERGY_ENTITY)}):
                EntitySelector(EntitySelectorConfig(domain="sensor", device_class=["energy", "power"])),
            vol.Optional(OPT_THRESHOLD_W, default=current.get(OPT_THRESHOLD_W, DEFAULT_THRESHOLD_W)):
                NumberSelector(NumberSelectorConfig(min=1, max=5000, step=1, unit_of_measurement="W",
                                                    mode=NumberSelectorMode.BOX)),
        })
        return self.async_show_form(
            step_id="load", data_schema=schema, errors=errors,
            description_placeholders={"load": str(load.get("name") or self._load_id)},
        )
