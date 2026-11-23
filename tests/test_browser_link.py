from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from custom_components.mijnslimstroom.const import DOMAIN

APP = "https://app.mijnslimstroom.nl"


async def test_linking_through_the_browser(hass: HomeAssistant, hass_client_no_auth, aioclient_mock,
                                           current_request_with_host) -> None:
    assert await async_setup_component(hass, "auth", {})
    menu = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert menu["type"] is FlowResultType.MENU and set(menu["menu_options"]) == {"browser", "manual"}
    step = await hass.config_entries.flow.async_configure(menu["flow_id"], {"next_step_id": "browser"})
    assert step["type"] is FlowResultType.EXTERNAL_STEP
    url = step["url"]
    assert url.startswith(APP + "/koppelen?")
    assert "client_id=home-assistant" in url and "code_challenge=" in url and "code_challenge_method=S256" in url

    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": menu["flow_id"], "redirect_uri": "https://example.com/auth/external/callback"})
    client = await hass_client_no_auth()
    assert (await client.get(f"/auth/external/callback?code=synthetic-code&state={state}")).status == 200

    aioclient_mock.post(APP + "/api/oauth/token", json={
        "access_token": "synthetic-test-code", "refresh_token": "synthetic-test-code",
        "token_type": "Bearer", "expires_in": 315360000})
    aioclient_mock.get(APP + "/api/whoami", json={"username": "testuser", "site_id": "thuis", "display_name": "Test"})
    aioclient_mock.get(APP + "/api/live", json={})
    result = await hass.config_entries.flow.async_configure(menu["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY, result
    assert result["data"]["access_token"] == "synthetic-test-code"
    assert result["data"]["username"] == "testuser" and result["data"]["site_id"] == "thuis"
    assert "password" not in result["data"]
    sent = aioclient_mock.mock_calls[0][2]
    assert sent["grant_type"] == "authorization_code" and sent["code"] == "synthetic-code" and sent["code_verifier"]


async def test_manual_step_still_takes_a_code(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(APP + "/api/whoami", json={"username": "testuser", "site_id": "thuis", "display_name": "Test"})
    menu = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    form = await hass.config_entries.flow.async_configure(menu["flow_id"], {"next_step_id": "manual"})
    assert form["type"] is FlowResultType.FORM and form["step_id"] == "manual"
    empty = await hass.config_entries.flow.async_configure(menu["flow_id"], {})
    assert empty["errors"] == {"base": "missing_credentials"}
    done = await hass.config_entries.flow.async_configure(menu["flow_id"], {"access_token": "synthetic-test-code"})
    assert done["type"] is FlowResultType.CREATE_ENTRY and done["title"] == "Test"
