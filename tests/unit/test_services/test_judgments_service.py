"""Tests for JudgmentsService."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from law_scrapper_mcp.client.saos_client import SaosClient
from law_scrapper_mcp.services.judgments_service import JudgmentsService
from law_scrapper_mcp.models.saos import CourtType, JudgmentType


class TestJudgmentsService:
    """Tests for judgments service."""

    @pytest.fixture
    async def service(self, mock_saos_client: SaosClient) -> JudgmentsService:
        """Create JudgmentsService instance."""
        return JudgmentsService(client=mock_saos_client)

    @respx.mock
    async def test_search_basic(self, service: JudgmentsService):
        """Test basic search with mapped output."""
        response_data = {
            "items": [
                {
                    "id": 1,
                    "href": "https://www.saos.org.pl/api/judgments/1",
                    "courtType": "COMMON",
                    "judgmentType": "SENTENCE",
                    "judgmentDate": "2023-01-01",
                    "courtCases": [{"caseNumber": "I ACa 1/23"}],
                    "judges": [{"name": "Jan Kowalski", "function": "PRESIDING_JUDGE"}],
                    "textContent": "Sample text",
                    "keywords": ["test"],
                    "division": {
                        "id": 1,
                        "name": "Wydział I",
                        "court": {"name": "Sąd Apelacyjny"}
                    }
                }
            ],
            "info": {
                "totalResults": 1
            }
        }
        respx.get("https://www.saos.org.pl/api/search/judgments").mock(
            return_value=Response(200, json=response_data)
        )

        output = await service.search(
            all_phrase="odszkodowanie",
            court_type="COMMON",
            judgment_types=["SENTENCE"],
        )

        assert output.total_count == 1
        assert output.returned_count == 1
        assert len(output.results) == 1
        assert output.results[0].id == 1
        assert output.results[0].courtType == CourtType.COMMON
        assert output.results[0].judgmentType == JudgmentType.SENTENCE
        assert output.results[0].courtCases[0].caseNumber == "I ACa 1/23"
        assert output.results[0].judges[0].name == "Jan Kowalski"
        assert "all=odszkodowanie" in output.query_summary
        assert "court_type=COMMON" in output.query_summary

    @respx.mock
    async def test_search_validation_law_journal(self, service: JudgmentsService):
        """Test search throws ValueError on invalid law journal entry format."""
        with pytest.raises(ValueError) as exc_info:
            await service.search(law_journal_entry_code="invalid_format")
        assert "Nieprawidłowy format kodu wpisu" in str(exc_info.value)

    @respx.mock
    async def test_search_validation_dates(self, service: JudgmentsService):
        """Test search throws ValueError on invalid date format."""
        with pytest.raises(ValueError) as exc_info:
            await service.search(judgment_date_from="2023/01/01")
        assert "Nieprawidłowy format daty" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            await service.search(judgment_date_to="01-01-2023")
        assert "Nieprawidłowy format daty" in str(exc_info.value)

    @respx.mock
    async def test_search_validation_page_size(self, service: JudgmentsService):
        """Test search throws ValueError on invalid page size."""
        with pytest.raises(ValueError) as exc_info:
            await service.search(page_size=5)
        assert "musi mieścić się w przedziale od 10 do 100" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            await service.search(page_size=105)
        assert "musi mieścić się w przedziale od 10 do 100" in str(exc_info.value)

    @respx.mock
    async def test_get_details(self, service: JudgmentsService):
        """Test getting full judgment details."""
        response_data = {
            "data": {
                "id": 123,
                "href": "https://www.saos.org.pl/api/judgments/123",
                "courtType": "SUPREME",
                "judgmentType": "DECISION",
                "judgmentDate": "2023-05-05",
                "courtCases": [{"caseNumber": "II CZ 5/23"}],
                "judges": [{"name": "Anna Nowak", "function": None}],
                "textContent": "Full text details",
                "keywords": ["key"],
                "division": None
            }
        }
        respx.get("https://www.saos.org.pl/api/judgments/123").mock(
            return_value=Response(200, json=response_data)
        )

        judgment = await service.get_details(123)
        assert judgment.id == 123
        assert judgment.courtType == CourtType.SUPREME
        assert judgment.judgmentType == JudgmentType.DECISION
        assert judgment.textContent == "Full text details"
        assert judgment.courtCases[0].caseNumber == "II CZ 5/23"
