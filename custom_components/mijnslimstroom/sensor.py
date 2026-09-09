"""Sensoren: live energiestromen, dagtotalen, saldo, prijs en plan."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DISPLAY_NAME, CONF_SITE_ID, DOMAIN
from .coordinator import MijnSlimstroomCoordinator


@dataclass(frozen=True, kw_only=True)
class SlimstroomSensorDescription(SensorEntityDescription):
    """Beschrijving + waarde-extractie uit de coordinator-data."""

    value_fn: Callable[[MijnSlimstroomCoordinator], Any]


def _live(key: str) -> Callable[[MijnSlimstroomCoordinator], Any]:
    return lambda c: (c.data.get("live") or {}).get(key)


def _today(key: str) -> Callable[[MijnSlimstroomCoordinator], Any]:
    return lambda c: (c.data.get("today") or {}).get(key)


SENSORS: tuple[SlimstroomSensorDescription, ...] = (
    # ---- live (elke minuut) ----
    SlimstroomSensorDescription(
        key="pv_w", translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_live("pv_w"),
    ),
    SlimstroomSensorDescription(
        key="load_w", translation_key="load_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_live("load_w"),
    ),
    SlimstroomSensorDescription(
        # + = laden, - = ontladen (Venus-conventie, zelfde als de app).
        key="battery_w", translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_live("battery_w"),
    ),
    SlimstroomSensorDescription(
        # + = import, - = export.
        key="grid_w", translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_live("grid_w"),
    ),
    SlimstroomSensorDescription(
        key="soc", translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_live("soc"),
    ),
    # ---- dagtotalen (om de 5 min; tellers resetten om middernacht,
    # total_increasing laat Home Assistant die reset zelf herkennen) ----
    SlimstroomSensorDescription(
        key="pv_kwh", translation_key="pv_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=_today("pv_kwh"),
    ),
    SlimstroomSensorDescription(
        key="load_kwh", translation_key="load_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=_today("load_kwh"),
    ),
    SlimstroomSensorDescription(
        key="grid_in_kwh", translation_key="grid_in_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=_today("grid_in_kwh"),
    ),
    SlimstroomSensorDescription(
        key="grid_out_kwh", translation_key="grid_out_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=_today("grid_out_kwh"),
    ),
    SlimstroomSensorDescription(
        key="to_battery_kwh", translation_key="to_battery_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=_today("to_battery_kwh"),
    ),
    SlimstroomSensorDescription(
        key="from_battery_kwh", translation_key="from_battery_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=_today("from_battery_kwh"),
    ),
    SlimstroomSensorDescription(
        key="self_sufficiency", translation_key="self_sufficiency_today",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=_today("self_sufficiency_pct"),
    ),
    # ---- geld & prijs ----
    SlimstroomSensorDescription(
        key="saldo_today", translation_key="saldo_today",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
        value_fn=lambda c: (c.data.get("earnings") or {}).get("eur_net"),
    ),
    SlimstroomSensorDescription(
        key="price", translation_key="current_price",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="EUR/kWh",
        suggested_display_precision=3,
        value_fn=lambda c: c.current_price_eur_per_kwh(),
    ),
    # ---- batterijplan (automatiseer op laden/ontladen/rust) ----
    SlimstroomSensorDescription(
        key="plan_action", translation_key="plan_action",
        device_class=SensorDeviceClass.ENUM,
        options=["laden", "ontladen", "rust"],
        value_fn=lambda c: c.current_plan_action(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MijnSlimstroomCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SlimstroomSensor(coordinator, entry, d) for d in SENSORS
    )


class SlimstroomSensor(CoordinatorEntity[MijnSlimstroomCoordinator], SensorEntity):
    """Een sensor op het gedeelde coordinator-datablok."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MijnSlimstroomCoordinator,
        entry: ConfigEntry,
        description: SlimstroomSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description: SlimstroomSensorDescription = description
        site = entry.data.get("site_id") or entry.entry_id
        self._attr_unique_id = f"{site}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, site)},
            name=entry.data.get("display_name") or f"Mijn SlimStroom {site}",
            manufacturer="Mijn SlimStroom",
            model="Thuisbatterij",
            configuration_url="https://app.mijnslimstroom.nl",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)
