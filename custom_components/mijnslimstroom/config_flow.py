"""Config flow: inloggen met de app-gegevens van Mijn SlimStroom."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
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
    METERS,
    OPT_ENERGY_ENTITY,
    OPT_LOADS,
    OPT_METERS,
    OPT_RUNNING_ENTITY,
    OPT_THRESHOLD_W,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ACCESS_TOKEN): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)
STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ACCESS_TOKEN): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


def _credentials(user_input: dict[str, Any], username: str = "") -> dict[str, str] | None:
    """Een koppelcode, of gebruikersnaam met wachtwoord; None als geen van beide compleet is."""
    code = (user_input.get(CONF_ACCESS_TOKEN) or "").strip()
    if code:
        return {CONF_ACCESS_TOKEN: code}
    name = (user_input.get(CONF_USERNAME) or username).strip()
    password = user_input.get(CONF_PASSWORD) or ""
    if name and password:
        return {CONF_USERNAME: name, CONF_PASSWORD: password}
    return None


def _api(hass, credentials: dict[str, str]) -> MijnSlimstroomApi:
    return MijnSlimstroomApi(
        async_get_clientsession(hass),
        credentials.get(CONF_USERNAME, ""),
        credentials.get(CONF_PASSWORD, ""),
        access_token=credentials.get(CONF_ACCESS_TOKEN),
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
        credentials = _credentials(user_input) if user_input is not None else None
        if user_input is not None and credentials is None:
            errors["base"] = "missing_credentials"
        elif credentials is not None:
            api = _api(self.hass, credentials)
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
                username = api.username or ""
                await self.async_set_unique_id(f"{username}:{api.site_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=api.display_name or api.site_id or username,
                    data={
                        CONF_USERNAME: username,
                        **credentials,
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
        credentials = (
            _credentials(user_input, entry.data.get(CONF_USERNAME, "")) if user_input is not None else None
        )
        if user_input is not None and credentials is None:
            errors["base"] = "missing_credentials"
        elif credentials is not None:
            api = _api(self.hass, credentials)
            try:
                await api.login()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except MijnSlimstroomError as e:
                _LOGGER.warning("Verbinden mislukt: %s", e)
                errors["base"] = "cannot_connect"
            else:
                kept = {k: v for k, v in entry.data.items() if k not in (CONF_PASSWORD, CONF_ACCESS_TOKEN)}
                return self.async_update_reload_and_abort(entry, data={**kept, **credentials})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
        )


class MijnSlimstroomOptionsFlow(OptionsFlow):
    """Menu met twee wegen. Slimme apparaten: per apparaat (uit de app)
    de entiteiten waarmee de integratie draaibeurten terugmeldt, een
    loopt-entiteit en/of een energie-entiteit; "Klaar" slaat op.
    Meters: per meter (warmtepomp, laadpaal, extra zonnepanelen) een
    kWh-teller waarvan de stand elke vijf minuten wordt doorgegeven."""

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}
        self._load_id: str | None = None

    def _loads(self) -> list[dict]:
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None or not coordinator.smart_enabled():
            return []
        return list(coordinator.smart().get("loads") or [])

    def _init_options(self) -> None:
        if not self._options:
            cur = self.config_entry.options or {}
            self._options = {OPT_LOADS: dict(cur.get(OPT_LOADS) or {}),
                             OPT_METERS: dict(cur.get(OPT_METERS) or {})}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._init_options()
        return self.async_show_menu(step_id="init", menu_options=["loads", "meters"])

    async def async_step_meters(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._init_options()
        errors: dict[str, str] = {}
        current = dict(self._options[OPT_METERS])
        if user_input is not None:
            chosen = {m: user_input.get(m) or None for m in METERS}
            for meter, entity_id in chosen.items():
                if not entity_id:
                    continue
                st = self.hass.states.get(entity_id)
                unit = str((st.attributes.get("unit_of_measurement") if st else "") or "").lower()
                if unit not in ("kwh", "wh", "mwh"):
                    errors[meter] = "meter_needs_kwh"
            if not errors:
                self._options[OPT_METERS] = {m: e for m, e in chosen.items() if e}
                return self.async_create_entry(title="", data=self._options)
            current = chosen
        schema = vol.Schema({
            vol.Optional(m, description={"suggested_value": current.get(m)}):
                EntitySelector(EntitySelectorConfig(domain="sensor", device_class="energy"))
            for m in METERS
        })
        return self.async_show_form(step_id="meters", data_schema=schema, errors=errors)

    async def async_step_loads(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._init_options()
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
            step_id="loads",
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
                return await self.async_step_loads()
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
                return await self.async_step_loads()
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
