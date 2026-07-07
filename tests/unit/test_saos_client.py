"""Tests for SaosClient."""

from __future__ import annotations

import pytest
import respx
import httpx
from httpx import Response

from law_scrapper_mcp.client.saos_client import SaosClient
from law_scrapper_mcp.client.exceptions import (
    ApiUnavailableError,
    JudgmentNotFoundError,
    SaosApiError,
)


class TestSaosClient:
    """Unit tests for SaosClient."""

    @respx.mock
    async def test_search_judgments_success(self, mock_saos_client: SaosClient):
        """Test search_judgments client method."""
        response_data = {"items": [], "info": {"totalResults": 0}}
        respx.get("https://www.saos.org.pl/api/search/judgments").mock(
            return_value=Response(200, json=response_data)
        )

        result = await mock_saos_client.search_judgments(all="test")
        assert result == response_data

    @respx.mock
    async def test_get_judgment_success(self, mock_saos_client: SaosClient):
        """Test get_judgment client method with ID."""
        response_data = {"data": {"id": 123}}
        respx.get("https://www.saos.org.pl/api/judgments/123").mock(
            return_value=Response(200, json=response_data)
        )

        result = await mock_saos_client.get_judgment(123)
        assert result == response_data

    @respx.mock
    async def test_get_judgment_by_href_success(self, mock_saos_client: SaosClient):
        """Test get_judgment client method with full URL."""
        response_data = {"data": {"id": 123}}
        respx.get("https://www.saos.org.pl/api/judgments/123").mock(
            return_value=Response(200, json=response_data)
        )

        result = await mock_saos_client.get_judgment("https://www.saos.org.pl/api/judgments/123")
        assert result == response_data

    @respx.mock
    async def test_get_judgment_not_found(self, mock_saos_client: SaosClient):
        """Test get_judgment throws JudgmentNotFoundError on 404 and is NOT retried."""
        route = respx.get("https://www.saos.org.pl/api/judgments/999").mock(
            return_value=Response(404)
        )

        mock_saos_client._circuit_breaker.reset()

        with pytest.raises(JudgmentNotFoundError) as exc_info:
            await mock_saos_client.get_judgment(999)
        assert "Nie znaleziono orzeczenia: 999" in str(exc_info.value)
        assert exc_info.value.status_code == 404
        assert route.call_count == 1
        assert mock_saos_client._circuit_breaker.failure_count == 0

    @respx.mock
    async def test_get_judgment_api_unavailable_retries_and_trips_breaker(self, mock_saos_client: SaosClient):
        """Test get_judgment retries 3 times on 503 but records exactly 1 logical failure."""
        route = respx.get("https://www.saos.org.pl/api/judgments/123").mock(
            return_value=Response(503)
        )

        mock_saos_client._circuit_breaker.reset()

        with pytest.raises(ApiUnavailableError) as exc_info:
            await mock_saos_client.get_judgment(123)
        assert "API SAOS tymczasowo niedostępne: 503" in str(exc_info.value)
        assert route.call_count == 3
        assert mock_saos_client._circuit_breaker.failure_count == 1

    @respx.mock
    async def test_get_judgment_other_error_not_retried(self, mock_saos_client: SaosClient):
        """Test get_judgment throws SaosApiError on generic 400 error and is NOT retried."""
        route = respx.get("https://www.saos.org.pl/api/judgments/123").mock(
            return_value=Response(400, text="Bad Request")
        )

        mock_saos_client._circuit_breaker.reset()

        with pytest.raises(SaosApiError) as exc_info:
            await mock_saos_client.get_judgment(123)
        assert "Błąd HTTP 400" in str(exc_info.value)
        assert route.call_count == 1
        assert mock_saos_client._circuit_breaker.failure_count == 0

    @respx.mock
    async def test_get_judgment_timeout_retries(self, mock_saos_client: SaosClient):
        """Test that timeouts are retried 3 times and register exactly 1 logical failure."""
        route = respx.get("https://www.saos.org.pl/api/judgments/123").mock(
            side_effect=httpx.TimeoutException("Connection timed out")
        )

        mock_saos_client._circuit_breaker.reset()

        with pytest.raises(ApiUnavailableError):
            await mock_saos_client.get_judgment(123)

        assert route.call_count == 3
        assert mock_saos_client._circuit_breaker.failure_count == 1

    @respx.mock
    async def test_circuit_breaker_prevents_execution(self, mock_saos_client: SaosClient):
        """Test that circuit breaker prevents requests when open."""
        respx.get("https://www.saos.org.pl/api/judgments/123").mock(
            return_value=Response(503)
        )

        # Set low failure threshold (e.g. 2 failures) to trip quickly
        mock_saos_client._circuit_breaker._failure_threshold = 2
        mock_saos_client._circuit_breaker.reset()

        # Failure 1 (retries 3 times internally, records 1 failure)
        with pytest.raises(ApiUnavailableError):
            await mock_saos_client.get_judgment(123)
        assert mock_saos_client._circuit_breaker.state == "closed"

        # Failure 2 (retries 3 times internally, records 2nd failure, trips breaker)
        with pytest.raises(ApiUnavailableError):
            await mock_saos_client.get_judgment(123)
        assert mock_saos_client._circuit_breaker.state == "open"

        # 3rd call fails immediately with circuit breaker open error (no HTTP requests made)
        with pytest.raises(ApiUnavailableError) as exc_info:
            await mock_saos_client.get_judgment(123)
        assert "circuit breaker otwarty" in str(exc_info.value)
