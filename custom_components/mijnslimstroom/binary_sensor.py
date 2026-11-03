"""Binaire sensoren voor de slimme momenten: per apparaat "nu gunstig"
(het moment om een automatisering te starten) en "negatieve prijs nu".
Alleen aangemaakt zodra de klant de slimme momenten aanzet."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MijnSlimstroomCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MijnSlimstroomCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[str] = set()

    def _sync() -> None:
        if not coordinator.smart_enabled():
            return
        new: list[BinarySensorEntity] = []
        if "_negative" not in known:
            known.add("_negative")
            new.append(SmartNegativePriceNow(coordinator, entry))
        for load in coordinator.smart().get("loads") or []:
            lid = str(load.get("id") or "")
            if lid and lid not in known:
                known.add(lid)
                new.append(SmartLoadActive(coordinator, entry, lid))
        if new:
            async_add_entities(new)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


class _Base(CoordinatorEntity[MijnSlimstroomCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: MijnSlimstroomCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        site = entry.data.get("site_id") or entry.entry_id
        self._attr_unique_id = f"{site}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, site)})


class SmartNegativePriceNow(_Base):
    _attr_translation_key = "smart_negative_now"

    def __init__(self, coordinator: MijnSlimstroomCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "smart_negative_now")

    @property
    def is_on(self) -> bool | None:
        neg = self.coordinator.smart().get("negative_price")
        return bool(neg.get("now")) if neg else None


class SmartLoadActive(_Base):
    """Aan zolang het aanbevolen venster van dit apparaat loopt."""

    _attr_translation_key = "smart_load_active"

    def __init__(self, coordinator: MijnSlimstroomCoordinator, entry: ConfigEntry, load_id: str) -> None:
        super().__init__(coordinator, entry, f"smart_{load_id}_active")
        self._load_id = load_id
        load = coordinator.smart_load(load_id) or {}
        self._attr_translation_placeholders = {"load": str(load.get("name") or load_id)}

    @property
    def is_on(self) -> bool | None:
        l = self.coordinator.smart_load(self._load_id)
        if not l or not l.get("available"):
            return None
        return bool(l.get("active_now"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        l = self.coordinator.smart_load(self._load_id) or {}
        return {"reden": l.get("reason"), "verwachting": bool(l.get("forecast"))}
