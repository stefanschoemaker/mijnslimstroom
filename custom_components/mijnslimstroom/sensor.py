"""Sensoren: live energiestromen, dagtotalen, saldo, prijs en plan."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
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
    SlimstroomSensorDescription(
        key="export_price", translation_key="export_price",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="EUR/kWh",
        suggested_display_precision=3,
        value_fn=lambda c: c.export_price_eur_per_kwh(),
    ),
    # ---- batterijplan (automatiseer op laden/ontladen/rust) ----
    SlimstroomSensorDescription(
        key="plan_action", translation_key="plan_action",
        device_class=SensorDeviceClass.ENUM,
        options=["laden", "ontladen", "rust"],
        value_fn=lambda c: c.current_plan_action(),
    ),
)


def _ts(v: Any) -> datetime | None:
    return datetime.fromtimestamp(int(v), timezone.utc) if v else None


# ---- slimme momenten: alleen aangemaakt als de klant ze aanzet ----
SMART_SENSORS: tuple[SlimstroomSensorDescription, ...] = (
    SlimstroomSensorDescription(
        key="smart_price_tier", translation_key="smart_price_tier",
        device_class=SensorDeviceClass.ENUM,
        options=["goedkoop", "normaal", "duur"],
        value_fn=lambda c: c.smart().get("price_tier_now"),
    ),
    SlimstroomSensorDescription(
        key="smart_best_2h_start", translation_key="smart_best_2h_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: _ts((c.smart().get("best_2h") or {}).get("start")),
    ),
    SlimstroomSensorDescription(
        key="smart_negative_next", translation_key="smart_negative_next",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: _ts((c.smart().get("negative_price") or {}).get("next_start")),
    ),
    SlimstroomSensorDescription(
        key="smart_heating", translation_key="smart_heating",
        device_class=SensorDeviceClass.ENUM,
        options=["bijstoken", "normaal", "temperen"],
        value_fn=lambda c: (c.smart().get("heating") or {}).get("advice"),
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
    # Slimme momenten: de generieke sensoren plus per apparaat een
    # "beste start"-tijdstip en de besparing. Alleen zodra de klant ze
    # aanzet (de API zegt enabled: false tot die tijd); apparaten die
    # er later bijkomen verschijnen bij de volgende verversing.
    known: set[str] = set()

    def _sync() -> None:
        if not coordinator.smart_enabled():
            return
        new: list[SensorEntity] = []
        if "_generic" not in known:
            known.add("_generic")
            new.extend(SlimstroomSensor(coordinator, entry, d) for d in SMART_SENSORS)
        for load in coordinator.smart().get("loads") or []:
            lid = str(load.get("id") or "")
            if lid and lid not in known:
                known.add(lid)
                for what in ("start", "saving", "last_saving", "followed"):
                    new.append(SmartLoadSensor(coordinator, entry, lid, what))
        if new:
            async_add_entities(new)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


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


class SmartLoadSensor(CoordinatorEntity[MijnSlimstroomCoordinator], SensorEntity):
    """Per apparaat: beste starttijd (timestamp, met venster-einde, reden
    en 'verwachting' als attributen) of de besparing in euro."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MijnSlimstroomCoordinator, entry: ConfigEntry,
                 load_id: str, what: str) -> None:
        super().__init__(coordinator)
        self._load_id = load_id
        self._what = what
        site = entry.data.get("site_id") or entry.entry_id
        self._attr_unique_id = f"{site}_smart_{load_id}_{what}"
        self._attr_translation_key = f"smart_load_{what}"
        self._attr_translation_placeholders = {"load": self._load_name()}
        if what == "start":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif what == "followed":
            self._attr_native_unit_of_measurement = "%"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = "EUR"
            self._attr_suggested_display_precision = 2
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, site)})

    def _load(self) -> dict:
        return self.coordinator.smart_load(self._load_id) or {}

    def _load_name(self) -> str:
        return str(self._load().get("name") or self._load_id)

    def _stats(self) -> dict:
        return self._load().get("stats") or {}

    @property
    def native_value(self) -> Any:
        l = self._load()
        if self._what == "last_saving":
            last = self._stats().get("last_run") or {}
            return last.get("saving_eur")
        if self._what == "followed":
            return self._stats().get("followed_pct")
        if not l.get("available"):
            return None
        if self._what == "saving":
            return l.get("saving_eur")
        wins = l.get("windows") or []
        return _ts(wins[0]["start"]) if wins else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        l = self._load()
        wins = l.get("windows") or []
        if self._what in ("last_saving", "followed"):
            st = self._stats()
            last = st.get("last_run") or {}
            return {
                "apparaat": self._load_name(),
                "dagen": st.get("days"),
                "keren_gedraaid": st.get("runs"),
                "keren_gemeten": st.get("measured"),
                "op_aanbevolen_moment": st.get("followed"),
                "besparing_eur": st.get("saving_eur"),
                "kwh": st.get("kwh"),
                "loopt_sinds": _ts(st["running_since"]).isoformat() if st.get("running_since") else None,
                "laatste_start": _ts(last["started_at"]).isoformat() if last.get("started_at") else None,
                "laatste_kwh": last.get("kwh"),
                "laatste_op_aanbevolen_moment": last.get("in_window"),
                "gekalibreerd": bool(l.get("calibrated")),
                "vermogen_kw": l.get("effective_power_kw"),
                "draaitijd_min": l.get("effective_duration_min"),
            }
        return {
            "apparaat": self._load_name(),
            "venster_einde": _ts(wins[0]["end"]).isoformat() if wins else None,
            "vensters": [{"start": _ts(w["start"]).isoformat(), "einde": _ts(w["end"]).isoformat()} for w in wins],
            "reden": l.get("reason"),
            "verwachting": bool(l.get("forecast")),
            "nu_gunstig": bool(l.get("active_now")),
            "kosten_eur": l.get("cost_eur"),
            "kosten_nu_eur": l.get("cost_now_eur"),
        }
