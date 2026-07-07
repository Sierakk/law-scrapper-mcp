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
        """Test get_judgment throws JudgmentNotFoundError on 404."""
        respx.get("https://www.saos.org.pl/api/judgments/999").mock(
            return_value=Response(404)
        )

        with pytest.raises(JudgmentNotFoundError) as exc_info:
            await mock_saos_client.get_judgment(999)
        assert "Nie znaleziono orzeczenia: 999" in str(exc_info.value)
        assert exc_info.value.status_code == 404

    @respx.mock
    async def test_get_judgment_api_unavailable(self, mock_saos_client: SaosClient):
        """Test get_judgment throws ApiUnavailableError on 503."""
        respx.get("https://www.saos.org.pl/api/judgments/123").mock(
            return_value=Response(503)
        )

        with pytest.raises(ApiUnavailableError):
            await mock_saos_client.get_judgment(123)

    @respx.mock
    async def test_get_judgment_other_error(self, mock_saos_client: SaosClient):
        """Test get_judgment throws SaosApiError on generic error."""
        respx.get("https://www.saos.org.pl/api/judgments/123").mock(
            return_value=Response(400, text="Bad Request")
        )

        with pytest.raises(SaosApiError) as exc_info:
            await mock_saos_client.get_judgment(123)
        assert "Błąd HTTP 400" in str(exc_info.value)
