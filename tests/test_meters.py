"""Meters terugmelden: de optiestroom en de reporter."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mijnslimstroom.const import DOMAIN, OPT_LOADS, OPT_METERS
from custom_components.mijnslimstroom.meters import MeterReporter


def _entry(hass: HomeAssistant, options=None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={"username": "testuser", "password": "synthetic-test-pw-123"},
                            options=options or {})
    entry.add_to_hass(hass)
    return entry


async def test_options_menu_links_meters_and_keeps_the_linked_devices(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.wp_energie", "812.4", {"unit_of_measurement": "kWh", "device_class": "energy"})
    hass.states.async_set("sensor.wp_vermogen", "950", {"unit_of_measurement": "W", "device_class": "power"})
    entry = _entry(hass, {OPT_LOADS: {"boiler": {"running_entity": "switch.boiler"}}})
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["type"] == FlowResultType.MENU and set(flow["menu_options"]) == {"loads", "meters"}
    form = await hass.config_entries.options.async_configure(flow["flow_id"], {"next_step_id": "meters"})
    assert form["type"] == FlowResultType.FORM and form["step_id"] == "meters"
    bad = await hass.config_entries.options.async_configure(flow["flow_id"], {"heatpump": "sensor.wp_vermogen"})
    assert bad["errors"] == {"heatpump": "meter_needs_kwh"}
    done = await hass.config_entries.options.async_configure(flow["flow_id"], {"heatpump": "sensor.wp_energie"})
    assert done["type"] == FlowResultType.CREATE_ENTRY
    assert done["data"] == {OPT_LOADS: {"boiler": {"running_entity": "switch.boiler"}},
                            OPT_METERS: {"heatpump": "sensor.wp_energie"}}


async def test_reporter_sends_changed_counters_in_kwh(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.wp_energie", "812.4", {"unit_of_measurement": "kWh"})
    hass.states.async_set("sensor.laadpaal", "1500", {"unit_of_measurement": "Wh"})
    hass.states.async_set("sensor.zon", "unavailable", {"unit_of_measurement": "kWh"})
    entry = _entry(hass, {OPT_METERS: {"heatpump": "sensor.wp_energie", "ev_charger": "sensor.laadpaal",
                                       "solar": "sensor.zon", "gas": "sensor.x"}})
    api = AsyncMock()
    reporter = MeterReporter(hass, entry, api)
    with patch("custom_components.mijnslimstroom.meters.time.time", return_value=1000.0):
        await reporter._tick(None)
    sent = api.report_meters.call_args.args[0]
    assert sent == [{"meter": "heatpump", "kwh": 812.4, "at": 1000}, {"meter": "ev_charger", "kwh": 1.5, "at": 1000}]
    api.report_meters.reset_mock()
    with patch("custom_components.mijnslimstroom.meters.time.time", return_value=1300.0):
        await reporter._tick(None)
    api.report_meters.assert_not_called()
    hass.states.async_set("sensor.wp_energie", "812.9", {"unit_of_measurement": "kWh"})
    with patch("custom_components.mijnslimstroom.meters.time.time", return_value=1600.0):
        await reporter._tick(None)
    assert api.report_meters.call_args.args[0] == [{"meter": "heatpump", "kwh": 812.9, "at": 1600}]
    with patch("custom_components.mijnslimstroom.meters.time.time", return_value=1000.0 + 1900):
        await reporter._tick(None)
    assert [r["meter"] for r in api.report_meters.call_args.args[0]] == ["ev_charger"]
