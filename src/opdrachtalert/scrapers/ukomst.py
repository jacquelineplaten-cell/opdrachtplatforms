"""Ukomst.

WordPress met een custom post type "jobs" dat via de REST API open staat:

    GET https://ukomst.nl/wp-json/wp/v2/jobs?per_page=50&page=N

Het veld ``content`` in die API is bij Ukomst leeg; de omschrijving staat alleen
op de publieke pagina (het veld ``link``). Het zijn er maar een stuk of tien,
dus halen we ze allemaal op.
"""

from __future__ import annotations

import logging

from ..models import PlatformResultaat, Uitvraag
from .base import Ophaler, parse_datum, tekst_uit_html

log = logging.getLogger(__name__)

API = "https://ukomst.nl/wp-json/wp/v2/jobs"
PAGINAGROOTTE = 50
MAX_PAGINAS = 10

# Ukomst publiceert af en toe een storingsbericht als "job". Die willen we niet.
RUIS = ("we are down for maintenance", "sorry for the inconvenience")


def _veld(blok: object) -> str:
    if isinstance(blok, dict):
        return tekst_uit_html(str(blok.get("rendered") or ""))
    return tekst_uit_html(str(blok or ""))


def _schoon_veld(tekst: str) -> str:
    """Ukomst zet vaak alleen een streepje in content; dat is geen omschrijving."""
    return "" if len(tekst.strip(" -\u2013\u2014")) < 30 else tekst


def _is_ruis(titel: str) -> bool:
    laag = titel.lower()
    return any(fragment in laag for fragment in RUIS)


def _naar_uitvraag(post: dict) -> Uitvraag:
    locatie = post.get("locatie")
    return Uitvraag(
        platform="Ukomst",
        titel=_veld(post.get("title")),
        url=str(post.get("link") or ""),
        omschrijving=_schoon_veld(_veld(post.get("content"))),
        locatie=locatie if isinstance(locatie, str) else "",
        gepubliceerd=parse_datum(post.get("date")),
        extern_id=str(post.get("id") or ""),
    )


def haal_op(ophaler: Ophaler, max_details: int = 120, **_: object) -> list[PlatformResultaat]:
    uitvragen: list[Uitvraag] = []
    try:
        for pagina in range(1, MAX_PAGINAS + 1):
            data = ophaler.json(f"{API}?per_page={PAGINAGROOTTE}&page={pagina}")
            if not isinstance(data, list) or not data:
                break
            uitvragen.extend(_naar_uitvraag(p) for p in data if isinstance(p, dict))
            if len(data) < PAGINAGROOTTE:
                break
    except Exception as exc:  # noqa: BLE001
        melding = f"{type(exc).__name__}: {exc}"
        log.warning("Ukomst ophalen mislukt: %s", melding)
        if not uitvragen:
            return [PlatformResultaat(platform="Ukomst", gelukt=False, melding=melding)]

    schoon = [u for u in uitvragen if u.titel and not _is_ruis(u.titel)]
    overgeslagen = len(uitvragen) - len(schoon)

    mislukt = 0
    for uitvraag in schoon[:max_details]:
        if uitvraag.omschrijving or not uitvraag.url:
            continue
        try:
            uitvraag.omschrijving = tekst_uit_html(ophaler.haal(uitvraag.url).text)
        except Exception as exc:  # noqa: BLE001
            mislukt += 1
            log.debug("Ukomst detail mislukt voor %s: %s", uitvraag.url, exc)

    notities = []
    if overgeslagen:
        notities.append(f"{overgeslagen} storingsbericht(en) overgeslagen")
    if mislukt:
        notities.append(f"{mislukt} detailpagina's mislukt")
    return [
        PlatformResultaat(platform="Ukomst", uitvragen=schoon, melding="; ".join(notities))
    ]
