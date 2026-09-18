"""Gedeelde bouwstenen voor de platformscrapers."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
}


class Ophaler:
    """Dunne wrapper om requests met vaste headers, timeout en een pauze."""

    def __init__(self, timeout: int = 45, pauze: float = 0.4) -> None:
        self.sessie = requests.Session()
        self.sessie.headers.update(BROWSER_HEADERS)
        self.timeout = timeout
        self.pauze = pauze

    def haal(self, url: str, **kwargs) -> requests.Response:
        antwoord = self.sessie.get(url, timeout=self.timeout, **kwargs)
        antwoord.raise_for_status()
        time.sleep(self.pauze)
        return antwoord

    def json(self, url: str, **kwargs) -> object:
        kwargs.setdefault("headers", {})["Accept"] = "application/json"
        return self.haal(url, **kwargs).json()

    def soep(self, url: str, **kwargs) -> BeautifulSoup:
        return BeautifulSoup(self.haal(url, **kwargs).text, "lxml")


def tekst_uit_html(html: str) -> str:
    """Leesbare platte tekst uit een HTML-fragment of hele pagina."""
    soep = BeautifulSoup(html, "lxml")
    for tag in soep(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()
    return " ".join(soep.get_text(" ").split())


def parse_datum(waarde: Optional[str]) -> Optional[date]:
    """Datums uit de verschillende platforms naar een date, of None."""
    if not waarde:
        return None
    tekst = str(waarde).strip()
    if not tekst:
        return None
    if tekst.endswith("Z"):
        tekst = tekst[:-1]
    for opmaak in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(tekst[: len(opmaak) + 6], opmaak).date()
        except ValueError:
            continue
    try:  # ISO met tijdzone, bv. 2026-09-17T16:17:10.804766+02:00
        return datetime.fromisoformat(tekst).date()
    except ValueError:
        return None


def kies_details(kandidaten: list, max_details: int) -> tuple[list, str]:
    """De uitvragen waarvan we de omschrijving ophalen, plus een waarschuwing.

    De bovengrens is er om te voorkomen dat een platform met plotseling veel
    aanbod de run laat vastlopen. Kapt hij af, dan moet dat in de mail komen te
    staan: anders scoren de weggelaten uitvragen stilletjes op alleen hun titel.
    """
    if max_details <= 0:
        return [], ""
    if len(kandidaten) <= max_details:
        return kandidaten, ""
    weggelaten = len(kandidaten) - max_details
    return (
        kandidaten[:max_details],
        f"LET OP: {weggelaten} uitvragen zonder omschrijving beoordeeld "
        f"(bovengrens {max_details} bereikt, zie max_details_per_platform)",
    )


def uren_tekst(minimum: object, maximum: object) -> Optional[str]:
    """'32' of '16-24' uit een min/max-paar, of None als er niets bruikbaars is."""
    def getal(x: object) -> Optional[int]:
        try:
            waarde = int(float(str(x)))
        except (TypeError, ValueError):
            return None
        return waarde if waarde > 0 else None

    lo, hi = getal(minimum), getal(maximum)
    if lo and hi and lo != hi:
        return f"{lo}-{hi}"
    return str(lo or hi) if (lo or hi) else None
