"""Config flow: inloggen met de app-gegevens van Mijn SlimStroom."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InvalidAuth, MijnSlimstroomApi, MijnSlimstroomError
from .const import CONF_DISPLAY_NAME, CONF_SITE_ID, DOMAIN

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
