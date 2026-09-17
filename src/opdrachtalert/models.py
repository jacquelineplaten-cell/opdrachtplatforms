"""Datamodel voor een uitvraag en voor het resultaat van een platform."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


def _schoon(tekst: Optional[str]) -> str:
    if not tekst:
        return ""
    zonder_tags = re.sub(r"<[^>]+>", " ", tekst)
    zonder_entiteiten = (
        zonder_tags.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#039;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return " ".join(zonder_entiteiten.split())


@dataclass
class Uitvraag:
    """Eén opdracht/uitvraag van een platform."""

    platform: str
    titel: str
    url: str
    opdrachtgever: str = ""
    bron: str = ""   # merk binnen het platform, bv. HeadFirst of Between binnen Striive
    omschrijving: str = ""
    locatie: str = ""
    uren_per_week: Optional[str] = None
    tarief: str = ""
    startdatum: str = ""
    einddatum: str = ""
    sluitingsdatum: str = ""
    gepubliceerd: Optional[date] = None
    segment: str = ""
    extern_id: str = ""
    ook_op: list[str] = field(default_factory=list)  # andere platforms met dezelfde uitvraag

    def __post_init__(self) -> None:
        self.titel = _schoon(self.titel)
        self.opdrachtgever = _schoon(self.opdrachtgever)
        self.omschrijving = _schoon(self.omschrijving)
        self.locatie = _schoon(self.locatie)
        self.segment = _schoon(self.segment)

    @property
    def sleutel(self) -> str:
        """Stabiele identiteit, om te zien of we een uitvraag al eerder stuurden."""
        basis = self.extern_id or self.url or f"{self.platform}|{self.titel}"
        return hashlib.sha1(f"{self.platform}|{basis}".encode("utf-8")).hexdigest()[:16]

    @property
    def zoektekst(self) -> str:
        return " ".join(
            [self.titel, self.opdrachtgever, self.segment, self.locatie, self.omschrijving]
        )

    @property
    def leeftijd_dagen(self) -> Optional[int]:
        if not self.gepubliceerd:
            return None
        return (datetime.now().date() - self.gepubliceerd).days


@dataclass
class PlatformResultaat:
    """Wat één platform opleverde, inclusief of het misging."""

    platform: str
    uitvragen: list[Uitvraag] = field(default_factory=list)
    gelukt: bool = True
    melding: str = ""

    @property
    def aantal(self) -> int:
        return len(self.uitvragen)
