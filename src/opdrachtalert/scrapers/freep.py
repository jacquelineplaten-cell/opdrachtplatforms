"""Freep.

    GET https://api.freep.nl/v1/assignments
        -> lijst met samenvattingen (titel, segment, opdrachtgever, uren, tarief)

De omschrijving zit niet in die lijst, dus die halen we per uitvraag van
https://www.freep.nl/opdracht/<slug>. Dat zijn er honderden, daarom eerst een
goedkope voorselectie op titel plus segment en pas daarna de detailpagina's.
"""

from __future__ import annotations

import logging

from ..models import PlatformResultaat, Uitvraag
from .base import Ophaler, parse_datum, tekst_uit_html

log = logging.getLogger(__name__)

API = "https://api.freep.nl/v1/assignments"
DETAIL = "https://www.freep.nl/opdracht/{slug}"


def _naar_uitvraag(regel: dict) -> Uitvraag:
    slug = str(regel.get("slug") or "")
    # Freep vult rate_max soms met 0; dat is geen tarief maar "niet opgegeven".
    ruw_tarief = regel.get("rate_max")
    try:
        tarief = ruw_tarief if float(ruw_tarief) > 0 else None
    except (TypeError, ValueError):
        tarief = None
    return Uitvraag(
        platform="Freep",
        titel=str(regel.get("title") or ""),
        url=DETAIL.format(slug=slug),
        opdrachtgever=str(regel.get("company_name") or ""),
        locatie=str(regel.get("location_province") or ""),
        uren_per_week=str(regel.get("hours")) if regel.get("hours") else None,
        tarief=f"max €{tarief} p/u" if tarief else "",
        gepubliceerd=parse_datum(regel.get("created_date")),
        segment=str(regel.get("segment") or ""),
        extern_id=str(regel.get("id") or slug),
    )


def haal_op(
    ophaler: Ophaler,
    voorselectie=None,
    max_details: int = 120,
    **_: object,
) -> list[PlatformResultaat]:
    try:
        data = ophaler.json(API)
    except Exception as exc:  # noqa: BLE001
        melding = f"{type(exc).__name__}: {exc}"
        log.warning("Freep ophalen mislukt: %s", melding)
        return [PlatformResultaat(platform="Freep", gelukt=False, melding=melding)]

    if not isinstance(data, list):
        return [
            PlatformResultaat(
                platform="Freep", gelukt=False, melding="onverwacht antwoord van de API"
            )
        ]

    uitvragen = [_naar_uitvraag(r) for r in data if isinstance(r, dict)]
    kandidaten = _kies_details(uitvragen, voorselectie, max_details)

    opgehaald, mislukt = 0, 0
    for uitvraag in kandidaten:
        try:
            uitvraag.omschrijving = tekst_uit_html(ophaler.haal(uitvraag.url).text)
            opgehaald += 1
        except Exception as exc:  # noqa: BLE001
            mislukt += 1
            log.debug("Freep detail mislukt voor %s: %s", uitvraag.url, exc)

    melding = f"{opgehaald} omschrijvingen opgehaald"
    if mislukt:
        melding += f", {mislukt} detailpagina's mislukt"
    return [PlatformResultaat(platform="Freep", uitvragen=uitvragen, melding=melding)]


def _kies_details(uitvragen, voorselectie, maximum: int):
    """Alleen detailpagina's ophalen voor uitvragen die er kansrijk uitzien."""
    if voorselectie is None:
        return uitvragen[:maximum]
    kansrijk = [u for u in uitvragen if voorselectie(u)]
    return kansrijk[:maximum]
