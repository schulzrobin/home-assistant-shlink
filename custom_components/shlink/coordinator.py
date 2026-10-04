"""Data update coordinator for Shlink."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ShlinkApi, ShlinkApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN


class ShlinkCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Shlink data updates."""

    def __init__(self, hass, api: ShlinkApi) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api

    def _ranges(self) -> dict[str, tuple[str, str]]:
        """Build ranges in Home Assistant's configured local timezone."""
        now = dt_util.now()
        tz = now.tzinfo
        today = now.date()

        def at_midnight(day):
            return datetime.combine(day, time.min, tzinfo=tz)

        today_start = at_midnight(today)
        tomorrow_start = at_midnight(today + timedelta(days=1))
        yesterday_start = at_midnight(today - timedelta(days=1))
        seven_days_start = at_midnight(today - timedelta(days=6))
        thirty_days_start = at_midnight(today - timedelta(days=29))

        def iso(value: datetime) -> str:
            return value.isoformat()

        return {
            "today": (iso(today_start), iso(tomorrow_start)),
            "yesterday": (iso(yesterday_start), iso(today_start)),
            "7_days": (iso(seven_days_start), iso(tomorrow_start)),
            "30_days": (iso(thirty_days_start), iso(tomorrow_start)),
        }

    async def _stats_for_link(
        self,
        link: dict[str, Any],
        ranges: dict[str, tuple[str, str]],
    ) -> dict[str, int]:
        short_code = str(link.get("shortCode", ""))
        domain = link.get("domain") or None

        async def count(start: str, end: str) -> int:
            result = await self.api.get_short_url_visits(
                short_code,
                domain=domain,
                start_date=start,
                end_date=end,
            )
            return int(result["total"])

        results = await asyncio.gather(
            count(*ranges["today"]),
            count(*ranges["yesterday"]),
            count(*ranges["7_days"]),
            count(*ranges["30_days"]),
        )
        return {
            "today": results[0],
            "yesterday": results[1],
            "7_days": results[2],
            "30_days": results[3],
        }

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            links = await self.api.get_short_urls()
            ranges = self._ranges()

            # Global Shlink counters shown on the main integration device.
            global_visits = await self.api.get_global_visits_summary()
            total_views = global_visits["total_views"]
            non_bot_views = global_visits["total_non_bots"]
            bot_views = global_visits["total_bots"]
            orphan_views = global_visits["orphan_views"]

            # Limit concurrent link batches so large Shlink installations do
            # not hit the REST API with all links at exactly the same moment.
            semaphore = asyncio.Semaphore(5)

            async def guarded(link):
                async with semaphore:
                    return await self._stats_for_link(link, ranges)

            stats_results = await asyncio.gather(
                *(guarded(link) for link in links),
                return_exceptions=True,
            )
        except ShlinkApiError as err:
            raise UpdateFailed(str(err)) from err

        by_key: dict[str, dict[str, Any]] = {}
        stats: dict[str, dict[str, int]] = {}

        for link, link_stats in zip(links, stats_results):
            short_code = str(link.get("shortCode", ""))
            domain = str(link.get("domain") or "")
            key = f"{domain}|{short_code}"
            by_key[key] = link

            if isinstance(link_stats, Exception):
                self.logger.warning(
                    "Could not update period visit stats for %s: %s",
                    short_code,
                    link_stats,
                )
                stats[key] = {}
            else:
                stats[key] = link_stats

        return {
            "count": len(links),
            "total_views": total_views,
            "non_bot_views": non_bot_views,
            "bot_views": bot_views,
            "orphan_views": orphan_views,
            "links": by_key,
            "stats": stats,
        }
