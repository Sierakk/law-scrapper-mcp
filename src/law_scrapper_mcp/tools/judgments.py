"""Search court judgments tool."""

from __future__ import annotations

import contextlib
import json
import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP

from law_scrapper_mcp.models.saos import JudgmentSearchOutput
from law_scrapper_mcp.models.tool_outputs import EnrichedResponse
from law_scrapper_mcp.services.response_enrichment import judgment_search_hints
from law_scrapper_mcp.tools.error_handling import handle_tool_errors

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    """Register judgments search tool."""

    @mcp.tool(tags={"judgments"})
    @handle_tool_errors(
        default_factory=lambda e, kw: JudgmentSearchOutput(
            results=[], total_count=0, query_summary="", returned_count=0
        ),
    )
    async def search_judgments(
        all: Annotated[
            str | None,
            "Szukana fraza tekstowa (wyszukiwanie pełnotekstowe w całym dokumencie). Np. 'umowa', 'odszkodowanie'.",
        ] = None,
        case_number: Annotated[
            str | None,
            "Sygnatura sprawy (np. 'I ACa 1010/09').",
        ] = None,
        judgment_types: Annotated[
            list[str] | str | None,
            "Lista typów orzeczeń (np. SENTENCE, DECISION). Dostępne wartości: "
            "DECISION, RESOLUTION, SENTENCE, REGULATION, REASONS. "
            "Może być przekazane jako lista lub pojedynczy ciąg znaków.",
        ] = None,
        court_type: Annotated[
            str | None,
            "Typ sądu. Dostępne wartości: COMMON, SUPREME, ADMINISTRATIVE, "
            "CONSTITUTIONAL_TRIBUNAL, NATIONAL_APPEAL_CHAMBER.",
        ] = None,
        law_journal_entry_code: Annotated[
            str | None,
            "Kod wpisu w dzienniku ustaw odnoszącego się do orzeczenia, w formacie 'rok/pozycja' (np. '2012/270').",
        ] = None,
        referenced_regulation: Annotated[
            str | None,
            "Powołany przepis prawny w treści orzeczenia.",
        ] = None,
        judge_name: Annotated[
            str | None,
            "Imię i nazwisko sędziego.",
        ] = None,
        keywords: Annotated[
            list[str] | str | None,
            "Słowa kluczowe orzeczenia. Może być przekazane jako lista lub pojedynczy ciąg znaków.",
        ] = None,
        judgment_date_from: Annotated[
            str | None,
            "Data orzeczenia OD (format YYYY-MM-DD).",
        ] = None,
        judgment_date_to: Annotated[
            str | None,
            "Data orzeczenia DO (format YYYY-MM-DD).",
        ] = None,
        page_size: Annotated[
            str | int | None,
            "Maksymalna liczba wyników na stronę (10-100). Domyślnie 20. Domyślny limit wyników wynosi 20.",
        ] = None,
        page_number: Annotated[
            str | int | None,
            "Numer strony (indeksowany od 0). Domyślnie 0.",
        ] = None,
        sorting_field: Annotated[
            str | None,
            "Pole według którego sortować wyniki. Dostępne wartości: "
            "DATABASE_ID, JUDGMENT_DATE, REFERENCING_JUDGMENTS_COUNT.",
        ] = None,
        sorting_direction: Annotated[
            str | None,
            "Kierunek sortowania: 'ASC' lub 'DESC'.",
        ] = None,
        ctx: Context = None,
    ) -> str:
        """
        Wyszukaj orzeczenia sądowe w bazie SAOS (Sądów Powszechnych, Sądu Najwyższego itp.).

        Kiedy użyć:
        - Gdy szukasz wyroków lub postanowień sądu dla danej sprawy (po sygnaturze).
        - Gdy chcesz znaleźć orzeczenia dotyczące konkretnego sędziego lub słów kluczowych.
        - Gdy analizujesz orzecznictwo w kontekście konkretnego artykułu/pozycji Dziennika Ustaw.

        Kiedy NIE używać:
        - Gdy szukasz treści samych ustaw lub rozporządzeń (aktów zwartych w sejmie) -> użyj search_legal_acts.
        - Gdy znasz ELI aktu prawnego i chcesz zobaczyć jego powiązania -> użyj analyze_act_relationships.

        Przykłady:
        - search_judgments(all="odszkodowanie", court_type="COMMON") - Orzeczenia sądów powszechnych ws. odszkodowań
        - search_judgments(case_number="I ACa 1010/09") - Znajdź orzeczenie o konkretnej sygnaturze sprawy
        - search_judgments(judge_name="Andrzej Struzik") - Orzeczenia wydane przez danego sędziego
        - search_judgments(keywords=["przywrócenie terminu procesowego"]) - Szukaj po konkretnym słowie kluczowym
        - search_judgments(law_journal_entry_code="2012/270") - Orzeczenia powiązane z pozycją Dziennika Ustaw 2012/270
        """
        assert ctx is not None
        judgments_service = ctx.request_context.lifespan_context["judgments_service"]

        # Parse page size and number
        page_size_int = 20
        if page_size is not None:
            with contextlib.suppress(ValueError, TypeError):
                page_size_int = int(page_size)

        page_number_int = 0
        if page_number is not None:
            with contextlib.suppress(ValueError, TypeError):
                page_number_int = int(page_number)

        # Normalize list params
        norm_judgment_types: list[str] | None = None
        if judgment_types is not None:
            if isinstance(judgment_types, str):
                if judgment_types.startswith("[") and judgment_types.endswith("]"):
                    try:
                        norm_judgment_types = json.loads(judgment_types)
                    except json.JSONDecodeError:
                        norm_judgment_types = [judgment_types]
                else:
                    norm_judgment_types = [judgment_types]
            elif isinstance(judgment_types, list):
                norm_judgment_types = judgment_types

        norm_keywords: list[str] | None = None
        if keywords is not None:
            if isinstance(keywords, str):
                if keywords.startswith("[") and keywords.endswith("]"):
                    try:
                        norm_keywords = json.loads(keywords)
                    except json.JSONDecodeError:
                        norm_keywords = [keywords]
                else:
                    norm_keywords = [keywords]
            elif isinstance(keywords, list):
                norm_keywords = keywords

        # Perform search
        search_output = await judgments_service.search(
            all_phrase=all,
            case_number=case_number,
            judgment_types=norm_judgment_types,
            court_type=court_type,
            law_journal_entry_code=law_journal_entry_code,
            referenced_regulation=referenced_regulation,
            judge_name=judge_name,
            keywords=norm_keywords,
            judgment_date_from=judgment_date_from,
            judgment_date_to=judgment_date_to,
            page_size=page_size_int,
            page_number=page_number_int,
            sorting_field=sorting_field,
            sorting_direction=sorting_direction,
        )

        results = search_output.results
        total_count = search_output.total_count

        # SAOS search endpoint paginates itself, but let's make sure the client gets the exact requested limit
        effective_limit = page_size_int
        if len(results) > effective_limit:
            results = results[:effective_limit]

        # Calculate if there are more results available
        has_more = total_count > (page_number_int + 1) * page_size_int

        response = EnrichedResponse(
            data=JudgmentSearchOutput(
                results=results,
                total_count=total_count,
                query_summary=search_output.query_summary,
                returned_count=len(results),
                page_number=page_number_int,
                page_size=page_size_int,
            ),
            hints=judgment_search_hints(
                total_count=total_count,
                has_results=len(results) > 0,
                was_truncated=has_more,
                applied_limit=effective_limit,
            ),
        )

        return response.model_dump_json()
