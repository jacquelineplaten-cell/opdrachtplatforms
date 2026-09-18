"""Flextender.

Inloggen blijkt niet nodig. De openbare opdrachtenpagina op www.flextender.nl
haalt haar resultaten op bij WordPress:

    POST https://www.flextender.nl/wp-admin/admin-ajax.php
         action=kbs_flx_searchjobs  (+ kbs_flx_widget_config uit het formulier)
    -> {"resultHtml": "<alle openstaande opdrachten in één keer>"}

De paginering daar is client-side, dus één verzoek levert de volledige lijst.
Elke kaart noemt het aanvraagnummer, en met dat nummer is de volledige
omschrijving publiek op te halen:

    GET https://app.flextender.nl/nologin/jobdetails/<aanvraagnummer>

Eerder logde deze scraper in op app.flextender.nl. Dat werkte niet: bij een
afgewezen inlog geeft Flextender exact dezelfde loginpagina terug, zonder reden,
en ook een echte browser kwam er niet doorheen. Die route is vervallen; de
FLEXTENDER_*-secrets zijn niet meer nodig.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ..models import PlatformResultaat, Uitvraag
from .base import Ophaler, tekst_uit_html

log = logging.getLogger(__name__)

ZOEKPAGINA = "https://www.flextender.nl/opdrachten/"
AJAX = "https://www.flextender.nl/wp-admin/admin-ajax.php"
DETAIL = "https://app.flextender.nl/nologin/jobdetails/{nummer}"
ZOEKACTIE = "kbs_flx_searchjobs"

AANVRAAGNUMMER = re.compile(r"aanvraagnr=(\d+)")
MAANDEN = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}


def _zoekvelden(pagina: BeautifulSoup) -> dict[str, str]:
    """De verborgen velden van het zoekformulier, inclusief het widget-token."""
    for formulier in pagina.find_all("form"):
        actie = formulier.find("input", attrs={"name": "action"})
        if not actie or actie.get("value") != ZOEKACTIE:
            continue
        velden: dict[str, str] = {}
        for veld in formulier.find_all("input"):
            naam = veld.get("name")
            soort = (veld.get("type") or "").lower()
            # Vinkjes zijn filters; die laten we uit zodat we alles krijgen.
            if not naam or soort == "checkbox":
                continue
            velden[naam] = veld.get("value") or ""
        velden["kbs_flx_joblsrc_freetext"] = ""
        return velden
    raise RuntimeError("zoekformulier niet gevonden op de opdrachtenpagina")


def _samenvatting(kaart) -> dict[str, str]:
    """De labelrijtjes van een kaart als {label: waarde}."""
    velden: dict[str, str] = {}
    for rij in kaart.select(".css-summaryrow"):
        label = rij.select_one(".css-caption")
        waarde = rij.select_one(".css-value")
        if not label or not waarde:
            continue
        sleutel = " ".join(label.get_text(" ").split()).lower()
        tekst = " ".join(waarde.get_text(" ").split())
        # Een kaart herhaalt sommige velden; de eerste is de samenvatting,
        # de latere staan in het uitklapblok en zijn vaak vollediger.
        if tekst and (sleutel not in velden or len(tekst) > len(velden[sleutel])):
            velden[sleutel] = tekst
    return velden


def _nl_datum(waarde: str) -> str:
    """'23 september 2026 agenda' -> '23-09-2026'."""
    m = re.search(r"(\d{1,2})\s+([a-zé]+)\s+(\d{4})", waarde.lower())
    if not m:
        return ""
    dag, maandnaam, jaar = m.groups()
    maand = MAANDEN.get(maandnaam)
    return f"{int(dag):02d}-{maand:02d}-{jaar}" if maand else ""


def _uren(waarde: str) -> str | None:
    m = re.search(r"(\d{1,2})(?:\s*-\s*(\d{1,2}))?", waarde)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}" if m.group(2) else m.group(1)


def _uit_kaart(kaart) -> Uitvraag | None:
    titel_el = kaart.select_one(".css-jobtitle")
    if not titel_el:
        return None
    titel = " ".join(titel_el.get_text(" ").split())
    if not titel:
        return None

    link = kaart.get("data-kbslinkurl") or ""
    nummer_match = AANVRAAGNUMMER.search(link)
    velden = _samenvatting(kaart)
    nummer = nummer_match.group(1) if nummer_match else velden.get("aanvraagnummer", "")
    if not nummer:
        return None

    klant_el = kaart.select_one(".css-customer")
    return Uitvraag(
        platform="Flextender",
        titel=titel,
        url=DETAIL.format(nummer=nummer),
        opdrachtgever=" ".join(klant_el.get_text(" ").split()) if klant_el else "",
        locatie=velden.get("regio", ""),
        uren_per_week=_uren(velden.get("uren per week", "")),
        startdatum=velden.get("start", ""),
        sluitingsdatum=_nl_datum(velden.get("einde inschrijfdatum", "")),
        segment=velden.get("duur", ""),
        extern_id=nummer,
    )


def haal_op(
    ophaler: Ophaler,
    voorselectie=None,
    max_details: int = 300,
    **_: object,
) -> list[PlatformResultaat]:
    try:
        pagina = ophaler.soep(ZOEKPAGINA)
        velden = _zoekvelden(pagina)
        # Het zoekformulier gaat als multipart de deur uit (FormData in de browser).
        antwoord = ophaler.sessie.post(
            AJAX,
            files={naam: (None, waarde) for naam, waarde in velden.items()},
            timeout=ophaler.timeout,
        )
        antwoord.raise_for_status()
        resultaat_html = (antwoord.json() or {}).get("resultHtml", "")
    except Exception as exc:  # noqa: BLE001
        melding = f"{type(exc).__name__}: {exc}"
        log.warning("Flextender ophalen mislukt: %s", melding)
        return [PlatformResultaat(platform="Flextender", gelukt=False, melding=melding)]

    if not resultaat_html:
        return [
            PlatformResultaat(
                platform="Flextender", gelukt=False, melding="lege zoekresultaten ontvangen"
            )
        ]

    soep = BeautifulSoup(resultaat_html, "lxml")
    gevonden: dict[str, Uitvraag] = {}
    for kaart in soep.select(".css-foundjob"):
        uitvraag = _uit_kaart(kaart)
        if uitvraag:
            gevonden.setdefault(uitvraag.extern_id, uitvraag)

    if not gevonden:
        return [
            PlatformResultaat(
                platform="Flextender",
                gelukt=False,
                melding="resultaten ontvangen maar geen opdrachten herkend (opmaak gewijzigd?)",
            )
        ]

    uitvragen = list(gevonden.values())
    kandidaten = uitvragen if voorselectie is None else [u for u in uitvragen if voorselectie(u)]

    opgehaald, mislukt, eerste_fout = 0, 0, ""
    for uitvraag in kandidaten[:max_details]:
        try:
            uitvraag.omschrijving = tekst_uit_html(ophaler.haal(uitvraag.url).text)
            opgehaald += 1
        except Exception as exc:  # noqa: BLE001
            mislukt += 1
            if not eerste_fout:
                eerste_fout = f"{type(exc).__name__}: {exc}"
            log.debug("Flextender detail mislukt voor %s: %s", uitvraag.url, exc)

    melding = f"{opgehaald} omschrijvingen opgehaald"
    if mislukt:
        melding += f", {mislukt} mislukt ({eerste_fout})"
    return [PlatformResultaat(platform="Flextender", uitvragen=uitvragen, melding=melding)]
