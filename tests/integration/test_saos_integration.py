"""Integration tests for SAOS API client and service."""

from __future__ import annotations

import pytest

from law_scrapper_mcp.client.cache import TTLCache
from law_scrapper_mcp.client.saos_client import SaosClient
from law_scrapper_mcp.services.judgments_service import JudgmentsService

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
async def saos_client() -> SaosClient:
    """Create a live SaosClient."""
    cache = TTLCache(max_entries=10)
    client = SaosClient(cache=cache, timeout=30.0, max_concurrent=2)
    await client.start()
    yield client
    await client.close()
    await cache.clear()


@pytest.fixture
def judgments_service(saos_client: SaosClient) -> JudgmentsService:
    """Create JudgmentsService instance."""
    return JudgmentsService(client=saos_client)


async def test_live_saos_search(judgments_service: JudgmentsService):
    """Test live search on SAOS API."""
    output = await judgments_service.search(
        all_phrase="własność",
        page_size=10,
    )
    assert output.returned_count > 0
    assert output.total_count > 0
    assert len(output.results) > 0
    assert output.results[0].id is not None
    assert output.results[0].href is not None


async def test_live_saos_get_details(judgments_service: JudgmentsService):
    """Test live retrieval of judgment details by ID."""
    # First search to get a valid ID
    search_output = await judgments_service.search(
        all_phrase="własność",
        page_size=10,
    )
    assert len(search_output.results) > 0
    judgment_id = search_output.results[0].id

    # Get details
    details = await judgments_service.get_details(judgment_id)
    assert details.id == judgment_id
    assert details.href is not None
    assert details.textContent is not None
