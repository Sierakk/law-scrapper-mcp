"""Service for searching court judgments via SAOS API."""

from __future__ import annotations

import logging
import re
from typing import Any, TYPE_CHECKING

from law_scrapper_mcp.client.saos_client import SaosClient
from law_scrapper_mcp.config import settings
from law_scrapper_mcp.models.saos import (
    Judgment,
    JudgmentSearchOutput,
    SaosSearchResponse,
    LinkedActReference,
    LinkedActsOutput,
)

if TYPE_CHECKING:
    from law_scrapper_mcp.services.act_service import ActService

logger = logging.getLogger(__name__)


class JudgmentsService:
    """Service for searching and managing Polish court judgments."""

    def __init__(self, client: SaosClient, act_service: ActService | None = None):
        self._client = client
        self._act_service = act_service

    async def search(
        self,
        all_phrase: str | None = None,
        case_number: str | None = None,
        judgment_types: list[str] | None = None,
        court_type: str | None = None,
        law_journal_entry_code: str | None = None,
        referenced_regulation: str | None = None,
        judge_name: str | None = None,
        keywords: list[str] | None = None,
        judgment_date_from: str | None = None,
        judgment_date_to: str | None = None,
        page_size: int = 20,
        page_number: int = 0,
        sorting_field: str | None = None,
        sorting_direction: str | None = None,
    ) -> JudgmentSearchOutput:
        """Search for court judgments in SAOS API."""
        # Validation
        if law_journal_entry_code:
            if not re.match(r"^\d{4}/\d+$", law_journal_entry_code):
                raise ValueError(
                    f"Nieprawidłowy format kodu wpisu dziennika ustaw: {law_journal_entry_code}. "
                    f"Oczekiwany format: ROK/POZYCJA (np. 2024/123)"
                )

        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        if judgment_date_from and not re.match(date_pattern, judgment_date_from):
            raise ValueError(
                f"Nieprawidłowy format daty początkowej: {judgment_date_from}. Oczekiwany format: YYYY-MM-DD"
            )
        if judgment_date_to and not re.match(date_pattern, judgment_date_to):
            raise ValueError(
                f"Nieprawidłowy format daty końcowej: {judgment_date_to}. Oczekiwany format: YYYY-MM-DD"
            )

        if page_size < 10 or page_size > 100:
            raise ValueError("Rozmiar strony (page_size) musi mieścić się w przedziale od 10 do 100.")

        params: dict[str, Any] = {
            "pageSize": page_size,
            "pageNumber": page_number,
        }
        summary_parts = []

        if all_phrase:
            params["all"] = all_phrase
            summary_parts.append(f"all={all_phrase}")
        if case_number:
            params["caseNumber"] = case_number
            summary_parts.append(f"case_number={case_number}")
        if judgment_types:
            params["judgmentTypes"] = judgment_types
            summary_parts.append(f"judgment_types={','.join(judgment_types)}")
        if court_type:
            params["courtType"] = court_type
            summary_parts.append(f"court_type={court_type}")
        if law_journal_entry_code:
            params["lawJournalEntryCode"] = law_journal_entry_code
            summary_parts.append(f"law_journal_entry_code={law_journal_entry_code}")
        if referenced_regulation:
            params["referencedRegulation"] = referenced_regulation
            summary_parts.append(f"referenced_regulation={referenced_regulation}")
        if judge_name:
            params["judgeName"] = judge_name
            summary_parts.append(f"judge_name={judge_name}")
        if keywords:
            params["keywords"] = keywords
            summary_parts.append(f"keywords={','.join(keywords)}")
        if judgment_date_from:
            params["judgmentDateFrom"] = judgment_date_from
            summary_parts.append(f"date_from={judgment_date_from}")
        if judgment_date_to:
            params["judgmentDateTo"] = judgment_date_to
            summary_parts.append(f"date_to={judgment_date_to}")
        if sorting_field:
            params["sortingField"] = sorting_field
            summary_parts.append(f"sort={sorting_field}")
        if sorting_direction:
            params["sortingDirection"] = sorting_direction
            summary_parts.append(f"dir={sorting_direction}")

        # Call SAOS Client via search_judgments which delegates to get_json with cache_ttl
        data = await self._client.get_json(
            "search/judgments", params=params, cache_ttl=settings.cache_search_ttl
        )

        # Parse with Pydantic
        response_model = SaosSearchResponse.model_validate(data)

        total_results = response_model.info.totalResults if response_model.info else 0
        returned_count = len(response_model.items)

        query_summary = " | ".join(summary_parts) if summary_parts else "all judgments"

        return JudgmentSearchOutput(
            results=response_model.items,
            total_count=total_results,
            query_summary=query_summary,
            returned_count=returned_count,
            page_number=page_number,
            page_size=page_size,
        )

    async def get_details(self, judgment_id: int | str) -> Judgment:
        """Get full judgment details by ID."""
        data = await self._client.get_judgment(judgment_id)
        # SAOS wraps judgment in top-level 'data' field
        raw_judgment = data.get("data", {}) if isinstance(data, dict) else {}
        return Judgment.model_validate(raw_judgment)

    async def link_to_acts(self, judgment_id: int | str) -> LinkedActsOutput:
        """Link referenced regulations in a judgment to ELI acts."""
        # 1. Fetch full judgment details
        judgment = await self.get_details(judgment_id)

        # 2. Extract and map referenced regulations to ELI format DU/{year}/{pos}
        # Deduplicate repeating ELIs using a dictionary to map eli -> LinkedActReference
        # Unmappable (missing journalYear or journalEntry) are tracked separately
        mapped_dict: dict[str, LinkedActReference] = {}
        unmapped: list[LinkedActReference] = []

        for reg in judgment.referencedRegulations:
            if not reg.journalYear or not reg.journalEntry:
                unmapped.append(
                    LinkedActReference(
                        eli=None,
                        title=reg.journalTitle,  # Fallback to journalTitle
                        status=None,
                        text=reg.text,
                        journalTitle=reg.journalTitle,
                        is_linked=False,
                        error_message="Niemapowalne powołanie (brak roku lub pozycji)",
                    )
                )
                continue

            eli = f"DU/{reg.journalYear}/{reg.journalEntry}"

            # Deduplicate by combining texts if they differ
            if eli in mapped_dict:
                existing = mapped_dict[eli]
                texts = []
                if existing.text:
                    texts.append(existing.text)
                if reg.text and reg.text not in texts:
                    texts.append(reg.text)
                existing.text = "; ".join(texts) if texts else None
                continue

            mapped_dict[eli] = LinkedActReference(
                eli=eli,
                title=None,
                status=None,
                text=reg.text,
                journalTitle=reg.journalTitle,
                is_linked=False,
            )

        # 3. Resolve each ELI using ActService (graceful degradation)
        linked_count = 0
        if self._act_service:
            for eli, ref in mapped_dict.items():
                try:
                    act_details = await self._act_service.get_details(eli)
                    ref.title = act_details.title
                    ref.status = act_details.status
                    ref.is_linked = True
                    linked_count += 1
                except Exception as e:
                    logger.debug(f"Failed to resolve act {eli} from ELI: {e}")
                    ref.is_linked = False
                    ref.error_message = "nie znaleziono w ELI"
        else:
            for ref in mapped_dict.values():
                ref.is_linked = False
                ref.error_message = "Brak serwisu aktów Sejmu w systemie"

        # Combine mapped and unmapped
        all_linked_acts = list(mapped_dict.values()) + unmapped

        # summary message
        summary_parts = [
            f"judgment_id={judgment_id}",
            f"total_references={len(judgment.referencedRegulations)}",
            f"linked={linked_count}",
        ]
        query_summary = " | ".join(summary_parts)

        return LinkedActsOutput(
            judgment_id=judgment.id,
            linked_acts=all_linked_acts,
            total_references=len(judgment.referencedRegulations),
            linked_count=linked_count,
            query_summary=query_summary,
        )
