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
