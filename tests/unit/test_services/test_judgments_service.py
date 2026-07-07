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

    @respx.mock
    async def test_link_to_acts_success(self, mock_saos_client: SaosClient):
        """Test linking judgment to acts with mapping, deduplication and resolution."""
        from unittest.mock import AsyncMock
        from law_scrapper_mcp.models.tool_outputs import ActDetailOutput

        judgment_data = {
            "data": {
                "id": 123,
                "href": "https://www.saos.org.pl/api/judgments/123",
                "courtType": "COMMON",
                "judgmentType": "SENTENCE",
                "judgmentDate": "2023-01-01",
                "courtCases": [{"caseNumber": "I ACa 1/23"}],
                "judges": [{"name": "Jan Kowalski", "function": "PRESIDING_JUDGE"}],
                "textContent": "Treść",
                "keywords": ["test"],
                "division": None,
                "referencedRegulations": [
                    {
                        "journalTitle": "Ustawa o podatku dochodowym",
                        "journalYear": 2011,
                        "journalNo": 21,
                        "journalEntry": 112,
                        "text": "art. 21 ust. 1 pkt 38"
                    },
                    {
                        "journalTitle": "Ustawa o podatku dochodowym",
                        "journalYear": 2011,
                        "journalNo": 21,
                        "journalEntry": 112,
                        "text": "art. 21 ust. 1 pkt 39"
                    },
                    {
                        "journalTitle": "Ustawa o ochronie konkurencji",
                        "journalYear": 2007,
                        "journalNo": 50,
                        "journalEntry": 331,
                        "text": "art. 9"
                    },
                    {
                        "journalTitle": "Niemapowalne rozporządzenie",
                        "journalYear": None,
                        "journalNo": None,
                        "journalEntry": None,
                        "text": "par. 1"
                    }
                ]
            }
        }

        respx.get("https://www.saos.org.pl/api/judgments/123").mock(
            return_value=Response(200, json=judgment_data)
        )

        mock_act_service = AsyncMock()
        async def mock_get_details(eli, load_content=False):
            if eli == "DU/2011/112":
                return ActDetailOutput(
                    eli="DU/2011/112",
                    publisher="WDU",
                    year=2011,
                    pos=112,
                    title="Ustawa o podatku dochodowym od osób fizycznych",
                    status="obowiązujący",
                )
            elif eli == "DU/2007/331":
                raise Exception("Act not found in ELI")
            raise Exception("Unexpected eli")

        mock_act_service.get_details.side_effect = mock_get_details

        service = JudgmentsService(client=mock_saos_client, act_service=mock_act_service)
        output = await service.link_to_acts(123)

        assert output.judgment_id == 123
        assert output.total_references == 4
        assert len(output.linked_acts) == 3
        assert output.linked_count == 1

        # Check DU/2011/112 details
        act_1 = next(a for a in output.linked_acts if a.eli == "DU/2011/112")
        assert act_1.is_linked is True
        assert act_1.title == "Ustawa o podatku dochodowym od osób fizycznych"
        assert act_1.status == "obowiązujący"
        assert "art. 21 ust. 1 pkt 38" in act_1.text
        assert "art. 21 ust. 1 pkt 39" in act_1.text

        # Check DU/2007/331 details (graceful degradation)
        act_2 = next(a for a in output.linked_acts if a.eli == "DU/2007/331")
        assert act_2.is_linked is False
        assert act_2.error_message == "nie znaleziono w ELI"
        assert act_2.title is None
        assert act_2.text == "art. 9"

        # Check unmapped details
        act_3 = next(a for a in output.linked_acts if a.eli is None)
        assert act_3.is_linked is False
        assert act_3.error_message == "Niemapowalne powołanie (brak roku lub pozycji)"
        assert act_3.text == "par. 1"
        assert act_3.journalTitle == "Niemapowalne rozporządzenie"
