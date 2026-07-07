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


async def test_live_saos_search_with_lists(judgments_service: JudgmentsService):
    """Test live search on SAOS API using list parameters."""
    output = await judgments_service.search(
        all_phrase="własność",
        judgment_types=["SENTENCE", "DECISION"],
        page_size=10,
    )
    assert output.total_count > 0
    assert len(output.results) > 0
    assert output.results[0].judgmentType in ["SENTENCE", "DECISION"]


async def test_live_saos_link_to_acts(judgments_service: JudgmentsService):
    """Test live linking of judgments to ELI acts using real APIs."""
    # Find a judgment referencing a specific entry (which should have referencedRegulations)
    search_output = await judgments_service.search(
        law_journal_entry_code="2011/112",
        page_size=10,
    )
    if not search_output.results:
        # Fallback if no specific entry search works
        search_output = await judgments_service.search(
            all_phrase="ustawa",
            page_size=10,
        )

    assert len(search_output.results) > 0
    judgment_id = search_output.results[0].id

    output = await judgments_service.link_to_acts(judgment_id)
    assert output.judgment_id == judgment_id
    assert output.total_references >= 0

    # Verify details of any linked acts if available
    if output.linked_count > 0:
        linked_acts = [act for act in output.linked_acts if act.is_linked]
        assert len(linked_acts) > 0
        assert linked_acts[0].title is not None
        assert len(linked_acts[0].title) > 0
        assert linked_acts[0].eli is not None


