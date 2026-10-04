"""Small asynchronous client for the Shlink REST API."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import API_VERSIONS


class ShlinkApiError(Exception):
    """Base Shlink API error."""


class ShlinkAuthError(ShlinkApiError):
    """Authentication failed."""


class ShlinkApi:
    """Shlink REST API client."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        api_key: str,
        verify_ssl: bool = True,
    ) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._verify_ssl = verify_ssl
        self.api_version: str | None = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        headers = {
            "X-Api-Key": self._api_key,
            "Accept": "application/json",
        }
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                ssl=self._verify_ssl,
                timeout=20,
            ) as response:
                if response.status in (401, 403):
                    raise ShlinkAuthError("Invalid or unauthorized Shlink API key")
                response.raise_for_status()
                return await response.json()
        except ShlinkAuthError:
            raise
        except (ClientError, ClientResponseError, TimeoutError, ValueError) as err:
            raise ShlinkApiError(str(err)) from err

    async def detect_api_version(self) -> str:
        """Find a supported Shlink REST API version."""
        if self.api_version:
            return self.api_version

        last_error: Exception | None = None
        for version in API_VERSIONS:
            try:
                await self._request(
                    "GET",
                    f"/rest/v{version}/short-urls",
                    params={"page": 1, "itemsPerPage": 1},
                )
                self.api_version = version
                return version
            except ShlinkAuthError:
                raise
            except ShlinkApiError as err:
                last_error = err

        raise ShlinkApiError(
            f"No supported Shlink API version found: {last_error}"
        )

    async def get_short_urls(self) -> list[dict[str, Any]]:
        """Return all short URLs, following Shlink pagination."""
        version = await self.detect_api_version()
        page = 1
        items: list[dict[str, Any]] = []

        while True:
            payload = await self._request(
                "GET",
                f"/rest/v{version}/short-urls",
                params={"page": page, "itemsPerPage": 100},
            )

            container = payload.get("shortUrls", payload)
            data = container.get("data", []) if isinstance(container, dict) else []
            if not isinstance(data, list):
                raise ShlinkApiError("Unexpected response from Shlink short-urls endpoint")

            items.extend(data)

            pagination = container.get("pagination", {}) if isinstance(container, dict) else {}
            pages_count = pagination.get("pagesCount")
            current_page = pagination.get("currentPage", page)

            if pages_count is not None:
                if int(current_page) >= int(pages_count):
                    break
            elif len(data) < 100:
                break

            page += 1
            if page > 10000:
                raise ShlinkApiError("Pagination safety limit reached")

        return items

    async def get_short_url_visits(
        self,
        short_code: str,
        *,
        domain: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Return visit statistics for one short URL and date range.

        We only need the pagination summary. Asking for one item keeps the
        response small while pagination.totalItems gives the matching count.
        """
        from urllib.parse import quote

        version = await self.detect_api_version()
        params: dict[str, Any] = {
            "page": 1,
            "itemsPerPage": 1,
        }
        if domain:
            params["domain"] = domain
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        payload = await self._request(
            "GET",
            f"/rest/v{version}/short-urls/{quote(short_code, safe='')}/visits",
            params=params,
        )

        container = payload.get("visits", payload)
        if not isinstance(container, dict):
            raise ShlinkApiError("Unexpected response from Shlink visits endpoint")

        pagination = container.get("pagination") or {}
        data = container.get("data") or []

        total = pagination.get("totalItems")
        if total is None:
            # Defensive fallback for unusual/older responses.
            total = len(data) if isinstance(data, list) else 0

        return {
            "total": int(total or 0),
        }

    async def get_global_visits_summary(self) -> dict[str, int]:
        """Return Shlink global non-orphan and orphan visit summaries.

        Current Shlink versions return:
        {
          "visits": {
            "nonOrphanVisits": {"total": ..., "nonBots": ..., "bots": ...},
            "orphanVisits": {"total": ..., "nonBots": ..., "bots": ...}
          }
        }
        """
        version = await self.detect_api_version()
        payload = await self._request("GET", f"/rest/v{version}/visits")

        visits = payload.get("visits") or {}
        non_orphan = visits.get("nonOrphanVisits") or {}
        orphan = visits.get("orphanVisits") or {}

        return {
            "total_views": int(non_orphan.get("total", 0) or 0),
            "orphan_views": int(orphan.get("total", 0) or 0),
            "total_non_bots": int(non_orphan.get("nonBots", 0) or 0),
            "total_bots": int(non_orphan.get("bots", 0) or 0),
            "orphan_non_bots": int(orphan.get("nonBots", 0) or 0),
            "orphan_bots": int(orphan.get("bots", 0) or 0),
        }
