"""Pydantic models and enums for SAOS API responses and tool output."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CourtType(StrEnum):
    """Polish court types in SAOS."""

    COMMON = "COMMON"
    SUPREME = "SUPREME"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    CONSTITUTIONAL_TRIBUNAL = "CONSTITUTIONAL_TRIBUNAL"
    NATIONAL_APPEAL_CHAMBER = "NATIONAL_APPEAL_CHAMBER"


class JudgmentType(StrEnum):
    """Types of court judgments in SAOS."""

    DECISION = "DECISION"
    RESOLUTION = "RESOLUTION"
    SENTENCE = "SENTENCE"
    REGULATION = "REGULATION"
    REASONS = "REASONS"


class CourtCase(BaseModel):
    """Case number details."""

    model_config = ConfigDict(extra="ignore")

    caseNumber: str = Field(description="Sygnatura akt (np. I ACa 1010/09)")


class Judge(BaseModel):
    """Judge details."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(description="Imię i nazwisko sędziego")
    function: str | None = Field(default=None, description="Funkcja sędziego")


class Division(BaseModel):
    """Court division details."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str | None = None
    code: str | None = None
    court: dict[str, Any] | None = None


class ReferencedRegulation(BaseModel):
    """A referenced regulation inside a judgment."""

    model_config = ConfigDict(extra="ignore")

    journalTitle: str | None = Field(default=None, description="Tytuł pozycji Dz.U.")
    journalYear: int | None = Field(default=None, description="Rok Dz.U.")
    journalNo: int | None = Field(default=None, description="Numer dziennika")
    journalEntry: int | None = Field(default=None, description="Numer pozycji")
    text: str | None = Field(default=None, description="Powołany przepis tekstem")


class Judgment(BaseModel):
    """A court judgment from SAOS API."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="Identyfikator orzeczenia")
    href: str = Field(description="Bezpośredni link do orzeczenia w API SAOS")
    courtType: CourtType | str | None = Field(default=None, description="Typ sądu")
    judgmentType: JudgmentType | str | None = Field(default=None, description="Typ orzeczenia")
    judgmentDate: str | None = Field(default=None, description="Data orzeczenia (YYYY-MM-DD)")
    courtCases: list[CourtCase] = Field(default_factory=list, description="Sprawy powiązane")
    judges: list[Judge] = Field(default_factory=list, description="Skład sędziowski")
    textContent: str | None = Field(default=None, description="Treść orzeczenia")
    keywords: list[str] = Field(default_factory=list, description="Słowa kluczowe")
    division: Division | dict[str, Any] | None = Field(default=None, description="Wydział sądu")
    referencedRegulations: list[ReferencedRegulation] = Field(default_factory=list, description="Powołane przepisy")


class SaosInfo(BaseModel):
    """Meta information about search results."""

    model_config = ConfigDict(extra="ignore")

    totalResults: int = Field(default=0, description="Całkowita liczba znalezionych orzeczeń")


class SaosSearchResponse(BaseModel):
    """Raw response wrapper from SAOS search API."""

    model_config = ConfigDict(extra="ignore")

    items: list[Judgment] = Field(default_factory=list)
    info: SaosInfo | None = Field(default=None)


class JudgmentSearchOutput(BaseModel):
    """Output model for the search_judgments tool."""

    results: list[Judgment] = Field(description="Lista znalezionych orzeczeń")
    total_count: int = Field(description="Całkowita liczba znalezionych orzeczeń")
    query_summary: str = Field(description="Podsumowanie kryteriów zapytania")
    returned_count: int = Field(description="Liczba zwróconych orzeczeń")
    page_number: int | None = Field(default=None, description="Numer strony (indeksowany od 0)")
    page_size: int | None = Field(default=None, description="Rozmiar strony")


class LinkedActReference(BaseModel):
    """Metadata of an act linked from a judgment regulation reference."""

    model_config = ConfigDict(extra="ignore")

    eli: str | None = Field(default=None, description="ELI identyfikator aktu")
    title: str | None = Field(default=None, description="Tytuł aktu")
    status: str | None = Field(default=None, description="Status obowiązywania")
    text: str | None = Field(default=None, description="Powołany przepis tekstem ze źródła")
    journalTitle: str | None = Field(default=None, description="Tytuł dziennika ze źródła")
    is_linked: bool = Field(description="Czy udało się pobrać szczegóły z ELI")
    error_message: str | None = Field(default=None, description="Komunikat o błędzie pobierania z ELI")


class LinkedActsOutput(BaseModel):
    """Output model for link_judgment_to_acts tool."""

    model_config = ConfigDict(extra="ignore")

    judgment_id: int = Field(description="Identyfikator orzeczenia")
    linked_acts: list[LinkedActReference] = Field(default_factory=list, description="Lista powiązanych aktów")
    total_references: int = Field(description="Całkowita liczba powołań w orzeczeniu")
    linked_count: int = Field(description="Liczba zmapowanych i pobranych aktów z ELI")
    query_summary: str = Field(description="Podsumowanie powiązania")
