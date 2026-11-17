"""De prijsverwachting als attributen op de prijssensoren."""

from datetime import datetime
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.mijnslimstroom.coordinator import import_price, price_forecast
from custom_components.mijnslimstroom.sensor import SENSORS, SMART_SENSORS, SlimstroomSensor

T0 = 1794870000
PRICING = {
    "t": [T0, T0 + 900, T0 + 1800, T0 + 2700],
    "prices_eur_per_kwh": [0.10, None, 0.08, -0.02],
    "current_hour_idx": 0,
    "forecast_from": T0 + 1800,
}
DYNAMIC = {"contract": "dynamic", "supplier_margin_eur_per_kwh": 0.02, "tax_eur_per_kwh": 0.10, "vat_pct": 0.21}


async def test_prices_carry_the_customer_tariff_and_mark_the_forecast(hass: HomeAssistant) -> None:
    out = price_forecast(PRICING, DYNAMIC)
    rows = out["prijzen"]
    assert [datetime.fromisoformat(r["start"]).timestamp() for r in rows] == [T0, T0 + 1800, T0 + 2700]
    assert [r["prijs"] for r in rows] == [0.2662, 0.242, 0.121]
    assert [r["verwachting"] for r in rows] == [False, True, True]
    assert datetime.fromisoformat(out["verwachting_vanaf"]).timestamp() == T0 + 1800
    assert out["resolutie_min"] == 15


async def test_without_contract_or_forecast_the_list_is_the_bare_market_price(hass: HomeAssistant) -> None:
    out = price_forecast({**PRICING, "forecast_from": None}, None)
    assert [r["prijs"] for r in out["prijzen"]] == [0.10, 0.08, -0.02]
    assert not any(r["verwachting"] for r in out["prijzen"]) and out["verwachting_vanaf"] is None
    assert price_forecast(None, None) == {"prijzen": [], "verwachting_vanaf": None, "resolutie_min": 15}
    assert import_price(0.10, {"contract": "fixed", "fixed_eur_per_kwh": 0.31}) == 0.31


async def test_both_price_sensors_expose_the_list_and_keep_it_out_of_the_recorder(hass: HomeAssistant) -> None:
    coordinator = MagicMock()
    coordinator.price_forecast.return_value = price_forecast(PRICING, DYNAMIC)
    coordinator.current_price_eur_per_kwh.return_value = 0.2662
    entry = MagicMock(data={"site_id": "testsite"}, entry_id="x")
    by_key = {d.key: SlimstroomSensor(coordinator, entry, d) for d in (*SENSORS, *SMART_SENSORS)}
    price = by_key["price"].extra_state_attributes
    tier = by_key["smart_price_tier"].extra_state_attributes
    assert len(price["prijzen"]) == 3 and tier["prijzen"] == price["prijzen"] and tier["prijs"] == 0.2662
    assert by_key["pv_w"].extra_state_attributes is None
    assert "prijzen" in SlimstroomSensor._unrecorded_attributes
