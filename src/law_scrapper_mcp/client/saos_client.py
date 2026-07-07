"""Async HTTP client for SAOS API."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from law_scrapper_mcp.client.cache import TTLCache
from law_scrapper_mcp.client.circuit_breaker import CircuitBreaker
from law_scrapper_mcp.client.exceptions import (
    ApiUnavailableError,
    JudgmentNotFoundError,
    SaosApiError,
)

class _SaosServerError(Exception):
    """Helper exception for SAOS 5xx server errors to trigger tenacity retry."""

    def __init__(self, status_code: int, response: httpx.Response) -> None:
        super().__init__(f"Server error: {status_code}")
        self.status_code = status_code
        self.response = response


class SaosClient:
    """Async HTTP client for SAOS API with retry, caching and circuit breaker."""

    BASE_URL = "https://www.saos.org.pl/api"

    def __init__(
        self,
        cache: TTLCache,
        timeout: float = 30.0,
        max_concurrent: int = 10,
        circuit_breaker: CircuitBreaker | None = None,
    ):
        self._client: httpx.AsyncClient | None = None
        self._cache = cache
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._timeout = timeout
        self._circuit_breaker = circuit_breaker or CircuitBreaker()

    async def start(self) -> None:
        """Initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=5.0, read=self._timeout, write=10.0, pool=10.0
                ),
                headers={
                    "User-Agent": "law-scrapper-mcp/2.0",
                    "Accept": "application/json",
                },
                follow_redirects=True,
            )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, _SaosServerError)),
        reraise=True,
    )
    async def _execute_request_with_retry(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """Execute request with retry logic (only retries 5xx and timeouts)."""
        assert self._client is not None
        try:
            response = await self._client.request(method, url, **kwargs)
            if response.status_code >= 500:
                raise _SaosServerError(response.status_code, response)
            return response
        except httpx.TimeoutException:
            raise

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        """Make HTTP request with retry logic and circuit breaker.

        Args:
            method: HTTP method
            path: URL path (relative to BASE_URL)
            **kwargs: Additional httpx request parameters

        Returns:
            HTTP response

        Raises:
            JudgmentNotFoundError: If resource not found (404)
            ApiUnavailableError: If API is unavailable (502, 503) or circuit breaker open
            SaosApiError: For other HTTP errors
        """
        if not self._circuit_breaker.can_execute():
            raise ApiUnavailableError(
                "API SAOS tymczasowo niedostępne (circuit breaker otwarty)",
                status_code=503,
            )

        if self._client is None:
            await self.start()

        assert self._client is not None  # ensured by start()

        url = f"{self.BASE_URL}/{path.lstrip('/')}"

        async with self._semaphore:
            try:
                response = await self._execute_request_with_retry(method, url, **kwargs)
                
                # Check for 4xx errors (client errors) which are raised directly without retry
                if response.status_code >= 400:
                    if response.status_code == 404:
                        parts = path.rstrip("/").split("/")
                        judgment_id = parts[-1] if parts else path
                        raise JudgmentNotFoundError(judgment_id)
                    else:
                        raise SaosApiError(
                            f"Błąd HTTP {response.status_code}: {response.text}",
                            status_code=response.status_code,
                            url=url,
                        )

                # Successful real 2xx response
                self._circuit_breaker.record_success()
                return response
            except (httpx.TimeoutException, _SaosServerError) as e:
                # These are only raised when tenacity retries are exhausted (transient 5xx or timeouts)
                self._circuit_breaker.record_failure()

                status_code = 503
                if isinstance(e, _SaosServerError):
                    status_code = e.status_code

                raise ApiUnavailableError(
                    f"API SAOS tymczasowo niedostępne: {status_code}",
                    status_code=status_code,
                    url=url,
                ) from e

    async def get_json(
        self, path: str, params: dict[str, Any] | None = None, cache_ttl: int | None = None
    ) -> Any:
        """Get JSON response from API with optional caching.

        Args:
            path: URL path
            params: Query parameters
            cache_ttl: Cache TTL in seconds (None = no cache)

        Returns:
            Parsed JSON response
        """
        cache_key = None
        if cache_ttl is not None:
            cache_key = f"saos:json:{path}:{params or {}}"
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        response = await self._request("GET", path, params=params)
        data = response.json()

        if cache_key is not None and cache_ttl is not None:
            await self._cache.set(cache_key, data, cache_ttl)

        return data

    async def search_judgments(self, **params: Any) -> dict[str, Any]:
        """Search for judgments.

        Args:
            **params: Search parameters

        Returns:
            Search results as dict
        """
        return await self.get_json("search/judgments", params=params)

    async def get_judgment(self, judgment_id: int | str) -> dict[str, Any]:
        """Get judgment details by ID or href.

        Args:
            judgment_id: Judgment ID or full href URL

        Returns:
            Judgment details as dict
        """
        if isinstance(judgment_id, str) and "/api/" in judgment_id:
            path = judgment_id.split("/api/")[-1]
        else:
            path = f"judgments/{judgment_id}"
        return await self.get_json(path)
