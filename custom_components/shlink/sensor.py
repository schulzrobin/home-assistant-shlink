"""Sensors for the Shlink integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ShlinkCoordinator


PERIOD_SENSORS = (
    ("total", "Besuche", "mdi:cursor-default-click-outline"),
    ("today", "Besuche heute", "mdi:calendar-today"),
    ("yesterday", "Besuche gestern", "mdi:calendar-arrow-left"),
    ("7_days", "Besuche letzte 7 Tage", "mdi:calendar-week"),
    ("30_days", "Besuche letzte 30 Tage", "mdi:calendar-month"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Shlink sensors."""
    coordinator: ShlinkCoordinator = entry.runtime_data

    async_add_entities(
        [
            ShlinkTotalLinksSensor(coordinator, entry),
            ShlinkGlobalViewsSensor(coordinator, entry, "total"),
            ShlinkGlobalViewsSensor(coordinator, entry, "non_bots"),
            ShlinkGlobalViewsSensor(coordinator, entry, "bots"),
            ShlinkGlobalViewsSensor(coordinator, entry, "orphan"),
        ],
        True,
    )

    known: set[str] = set()

    @callback
    def add_new_short_links() -> None:
        new_entities = []
        for key in coordinator.data.get("links", {}):
            if key in known:
                continue
            known.add(key)
            for period, name, icon in PERIOD_SENSORS:
                new_entities.append(
                    ShlinkShortLinkSensor(
                        coordinator, entry, key, period, name, icon
                    )
                )
            new_entities.append(
                ShlinkShortUrlSensor(coordinator, entry, key)
            )
            new_entities.append(
                ShlinkLongUrlSensor(coordinator, entry, key)
            )
        if new_entities:
            async_add_entities(new_entities)

    add_new_short_links()
    entry.async_on_unload(coordinator.async_add_listener(add_new_short_links))


class ShlinkBaseEntity(CoordinatorEntity[ShlinkCoordinator], SensorEntity):
    """Base Shlink entity."""

    _attr_has_entity_name = True


class ShlinkTotalLinksSensor(ShlinkBaseEntity):
    """Total number of short links."""

    _attr_name = "Kurzlinks"
    _attr_icon = "mdi:link-variant"
    _attr_native_unit_of_measurement = "Links"

    def __init__(self, coordinator: ShlinkCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_total_short_links"
        self._entry = entry

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data.get("count", 0))

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_shlink")},
            name="Shlink",
            manufacturer="Shlink",
            model="URL Shortener",
            configuration_url=self.coordinator.api.base_url,
        )


class ShlinkGlobalViewsSensor(ShlinkBaseEntity):
    """Global Shlink visit counters."""

    _attr_native_unit_of_measurement = "Besuche"

    def __init__(
        self,
        coordinator: ShlinkCoordinator,
        entry: ConfigEntry,
        kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._kind = kind
        if kind == "orphan":
            self._attr_name = "Orphan Views"
            self._attr_icon = "mdi:link-off"
            self._attr_unique_id = f"{entry.entry_id}_orphan_views"
        elif kind == "non_bots":
            self._attr_name = "NonBots"
            self._attr_icon = "mdi:account-check-outline"
            self._attr_unique_id = f"{entry.entry_id}_non_bot_views"
        elif kind == "bots":
            self._attr_name = "Bots"
            self._attr_icon = "mdi:robot-outline"
            self._attr_unique_id = f"{entry.entry_id}_bot_views"
        else:
            self._attr_name = "Total"
            self._attr_icon = "mdi:eye-outline"
            # Keep the old unique ID so the existing Gesamt Views entity
            # is renamed instead of duplicated.
            self._attr_unique_id = f"{entry.entry_id}_total_views"

    @property
    def native_value(self) -> int:
        keys = {
            "total": "total_views",
            "non_bots": "non_bot_views",
            "bots": "bot_views",
            "orphan": "orphan_views",
        }
        return int(self.coordinator.data.get(keys[self._kind], 0))

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_shlink")},
            name="Shlink",
            manufacturer="Shlink",
            model="URL Shortener",
            configuration_url=self.coordinator.api.base_url,
        )


class ShlinkShortLinkSensor(ShlinkBaseEntity):
    """A statistic sensor belonging to one Shlink short URL device."""

    _attr_native_unit_of_measurement = "Besuche"

    def __init__(
        self,
        coordinator: ShlinkCoordinator,
        entry: ConfigEntry,
        key: str,
        period: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._period = period
        self._attr_name = name
        self._attr_icon = icon
        safe_key = key.replace("://", "_").replace("/", "_")
        suffix = "visits" if period == "total" else f"visits_{period}"
        self._attr_unique_id = f"{entry.entry_id}_shortlink_{safe_key}_{suffix}"

    @property
    def _link(self) -> dict[str, Any] | None:
        return self.coordinator.data.get("links", {}).get(self._key)

    @property
    def available(self) -> bool:
        if not super().available or self._link is None:
            return False
        if self._period == "total":
            return True
        return self._period in self.coordinator.data.get("stats", {}).get(self._key, {})

    @property
    def native_value(self) -> int | None:
        link = self._link
        if link is None:
            return None

        if self._period != "total":
            value = self.coordinator.data.get("stats", {}).get(self._key, {}).get(self._period)
            return int(value) if value is not None else None

        visits_summary = link.get("visitsSummary") or {}
        if isinstance(visits_summary, dict):
            for field in ("total", "nonBots"):
                value = visits_summary.get(field)
                if value is not None:
                    return int(value or 0)
        return int(link.get("visitsCount", 0) or 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # Put descriptive link metadata on the total sensor only to avoid
        # duplicating a large set of attributes on all period sensors.
        if self._period != "total":
            return {}

        link = self._link
        if link is None:
            return {}

        meta = link.get("meta") or {}
        return {
            "short_url": link.get("shortUrl"),
            "long_url": link.get("longUrl"),
            "short_code": link.get("shortCode"),
            "domain": link.get("domain"),
            "title": link.get("title"),
            "tags": link.get("tags", []),
            "date_created": link.get("dateCreated"),
            "valid_since": meta.get("validSince"),
            "valid_until": meta.get("validUntil"),
            "max_visits": meta.get("maxVisits"),
            "crawlable": link.get("crawlable"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        link = self._link or {}
        code = str(link.get("shortCode") or self._key.split("|", 1)[-1])
        domain = str(link.get("domain") or self._key.split("|", 1)[0] or "default")
        title = link.get("title")
        short_url = link.get("shortUrl")

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{domain}_{code}")},
            name=f"Shlink – {title or code}",
            manufacturer="Shlink",
            model="Kurzlink",
            configuration_url=short_url or self.coordinator.api.base_url,
            via_device=(DOMAIN, f"{self._entry.entry_id}_shlink"),
        )

class ShlinkShortUrlSensor(ShlinkBaseEntity):
    """Expose the short URL itself as a text-valued sensor."""

    _attr_name = "Short URL"
    _attr_icon = "mdi:link-variant"

    def __init__(
        self,
        coordinator: ShlinkCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        safe_key = key.replace("://", "_").replace("/", "_")
        self._attr_unique_id = f"{entry.entry_id}_shortlink_{safe_key}_short_url"

    @property
    def _link(self) -> dict[str, Any] | None:
        return self.coordinator.data.get("links", {}).get(self._key)

    @property
    def available(self) -> bool:
        return super().available and self._link is not None

    @property
    def native_value(self) -> str | None:
        link = self._link
        if link is None:
            return None
        return link.get("shortUrl")

    @property
    def device_info(self) -> DeviceInfo:
        link = self._link or {}
        code = str(link.get("shortCode") or self._key.split("|", 1)[-1])
        domain = str(link.get("domain") or self._key.split("|", 1)[0] or "default")
        title = link.get("title")
        short_url = link.get("shortUrl")

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{domain}_{code}")},
            name=f"Shlink – {title or code}",
            manufacturer="Shlink",
            model="Kurzlink",
            configuration_url=short_url or self.coordinator.api.base_url,
            via_device=(DOMAIN, f"{self._entry.entry_id}_shlink"),
        )

class ShlinkLongUrlSensor(ShlinkBaseEntity):
    """Expose the destination/long URL as a text-valued sensor."""

    _attr_name = "Long URL"
    _attr_icon = "mdi:link"

    def __init__(
        self,
        coordinator: ShlinkCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        safe_key = key.replace("://", "_").replace("/", "_")
        self._attr_unique_id = f"{entry.entry_id}_shortlink_{safe_key}_long_url"

    @property
    def _link(self) -> dict[str, Any] | None:
        return self.coordinator.data.get("links", {}).get(self._key)

    @property
    def available(self) -> bool:
        return super().available and self._link is not None

    @property
    def native_value(self) -> str | None:
        link = self._link
        if link is None:
            return None
        return link.get("longUrl")

    @property
    def device_info(self) -> DeviceInfo:
        link = self._link or {}
        code = str(link.get("shortCode") or self._key.split("|", 1)[-1])
        domain = str(link.get("domain") or self._key.split("|", 1)[0] or "default")
        title = link.get("title")
        short_url = link.get("shortUrl")

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{domain}_{code}")},
            name=f"Shlink – {title or code}",
            manufacturer="Shlink",
            model="Kurzlink",
            configuration_url=short_url or self.coordinator.api.base_url,
            via_device=(DOMAIN, f"{self._entry.entry_id}_shlink"),
        )

