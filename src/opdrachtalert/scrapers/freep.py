"""Freep.

Twee endpoints op dezelfde API-host:

    GET https://api.freep.nl/v1/assignments          -> alle uitvragen, samenvatting
    GET https://api.freep.nl/v1/assignment/<slug>/   -> één uitvraag, met omschrijving

De omschrijving zit niet in de lijst, dus die halen we per uitvraag op. Dat doen
we bewust via de API en niet via www.freep.nl/opdracht/<slug>: die website
weigert verzoeken vanaf datacenter-IP's (in GitHub Actions mislukte elke
detailpagina), terwijl api.freep.nl gewoon antwoordt. De API is bovendien zo'n
veertig keer kleiner per verzoek en geeft extra velden als de sluitingsdatum.

Het zijn er honderden, dus we halen alleen de detailpagina op van uitvragen die
de drempel nog kunnen halen (zie de voorselectie in main.py).
"""

from __future__ import annotations

import logging

from ..models import PlatformResultaat, Uitvraag
from .base import Ophaler, parse_datum, tekst_uit_html

log = logging.getLogger(__name__)

LIJST = "https://api.freep.nl/v1/assignments"
DETAIL = "https://api.freep.nl/v1/assignment/{slug}/"
PAGINA = "https://www.freep.nl/opdracht/{slug}"


def _tarief(regel: dict) -> str:
    def getal(waarde: object) -> float:
        try:
            return float(waarde)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    lo, hi = getal(regel.get("rate_min")), getal(regel.get("rate_max"))
    if lo and hi and lo != hi:
        return f"€{lo:.0f}-{hi:.0f} p/u"
    if hi or lo:
        return f"max €{hi or lo:.0f} p/u"
    return ""


def _datum_tekst(waarde: object) -> str:
    datum = parse_datum(waarde if isinstance(waarde, str) else None)
    return datum.strftime("%d-%m-%Y") if datum else ""


def _naar_uitvraag(regel: dict) -> Uitvraag:
    slug = str(regel.get("slug") or "")
    return Uitvraag(
        platform="Freep",
        titel=str(regel.get("title") or ""),
        url=PAGINA.format(slug=slug),
        opdrachtgever=str(regel.get("company_name") or ""),
        locatie=str(regel.get("location_name") or regel.get("location_province") or ""),
        uren_per_week=str(regel.get("hours")) if regel.get("hours") else None,
        tarief=_tarief(regel),
        gepubliceerd=parse_datum(regel.get("created_date")),
        segment=str(regel.get("segment") or ""),
        extern_id=str(regel.get("id") or slug),
    )


def _vul_aan(uitvraag: Uitvraag, detail: dict) -> None:
    """De detailrespons bevat alles wat de lijst heeft, plus de omschrijving."""
    uitvraag.omschrijving = tekst_uit_html(str(detail.get("content") or ""))
    uitvraag.startdatum = _datum_tekst(detail.get("start_date"))
    uitvraag.einddatum = _datum_tekst(detail.get("end_date"))
    uitvraag.sluitingsdatum = _datum_tekst(detail.get("closing_date"))
    if detail.get("location_name"):
        uitvraag.locatie = str(detail["location_name"])
    tarief = _tarief(detail)
    if tarief:
        uitvraag.tarief = tarief


def haal_op(
    ophaler: Ophaler,
    voorselectie=None,
    max_details: int = 300,
    **_: object,
) -> list[PlatformResultaat]:
    try:
        data = ophaler.json(LIJST)
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
    kandidaten = uitvragen if voorselectie is None else [u for u in uitvragen if voorselectie(u)]

    opgehaald, mislukt, eerste_fout = 0, 0, ""
    for uitvraag in kandidaten[:max_details]:
        slug = uitvraag.url.rsplit("/", 1)[-1]
        try:
            detail = ophaler.json(DETAIL.format(slug=slug))
            if isinstance(detail, dict):
                _vul_aan(uitvraag, detail)
                opgehaald += 1
            else:
                mislukt += 1
        except Exception as exc:  # noqa: BLE001
            mislukt += 1
            if not eerste_fout:
                eerste_fout = f"{type(exc).__name__}: {exc}"
            log.debug("Freep detail mislukt voor %s: %s", slug, exc)

    melding = f"{opgehaald} omschrijvingen opgehaald"
    if mislukt:
        melding += f", {mislukt} mislukt ({eerste_fout})"
    return [PlatformResultaat(platform="Freep", uitvragen=uitvragen, melding=melding)]
