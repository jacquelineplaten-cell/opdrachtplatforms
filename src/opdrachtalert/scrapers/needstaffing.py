"""Need Staffing.

Server-gerenderde HTML, 20 per pagina:

    GET https://needstaffing.nl/Opdrachten?PageNumber=N&SortOrder=NewestFirst

Elke kaart is één <a href="/Opdrachten/<id>"> met een <h2> als titel en een rij
informatieblokjes waarvan het icoon-alt vertelt wat er staat ("Locatie",
"Verwacht aantal uren per week", "Deadline voor reageren", ...). We lezen die
labels uit in plaats van de kaarttekst te ontleden, want de labels veranderen
minder snel dan de volgorde. De omschrijving staat op /Opdrachten/<id>.
"""

from __future__ import annotations

import logging
import re

from ..models import PlatformResultaat, Uitvraag
from .base import Ophaler, kies_details, tekst_uit_html

log = logging.getLogger(__name__)

BASIS = "https://needstaffing.nl"
LIJST = BASIS + "/Opdrachten?PageNumber={pagina}&SortOrder=NewestFirst"
MAX_PAGINAS = 15
DETAILPAD = re.compile(r"^/Opdrachten/\d+$")
OPDRACHTGEVER = re.compile(r"opdrachtgever\s+(.+?)\s+zijn wij op zoek", re.IGNORECASE)


def _informatie(kaart) -> dict[str, str]:
    """De informatieblokjes als {label uit het icoon-alt: waarde}."""
    velden: dict[str, str] = {}
    for blok in kaart.select(".vacancies-overview-item-information-item"):
        icoon = blok.find("img")
        label = (icoon.get("alt") or icoon.get("title") or "").strip().lower() if icoon else ""
        waarde = " ".join(blok.get_text(" ").split())
        if label and waarde:
            velden[label] = waarde
    return velden


def _uit_kaart(anker) -> Uitvraag | None:
    href = anker.get("href") or ""
    if not DETAILPAD.match(href):
        return None

    kop = anker.find(["h2", "h3"])
    titel = " ".join(kop.get_text(" ").split()) if kop else ""
    if not titel:
        return None

    samenvatting = anker.select_one(".vacancies-overview-item-summary")
    samenvatting_tekst = " ".join(samenvatting.get_text(" ").split()) if samenvatting else ""
    opdrachtgever_match = OPDRACHTGEVER.search(samenvatting_tekst)

    velden = _informatie(anker)
    uren = velden.get("verwacht aantal uren per week", "")
    duur = velden.get("verwachte periode", "")

    return Uitvraag(
        platform="Need Staffing",
        titel=titel,
        url=BASIS + href,
        opdrachtgever=opdrachtgever_match.group(1) if opdrachtgever_match else "",
        locatie=velden.get("locatie", ""),
        uren_per_week=uren or None,
        tarief=velden.get("verwachte compensatie", ""),
        startdatum=velden.get("verwachte startdatum", ""),
        sluitingsdatum=velden.get("deadline voor reageren", ""),
        # Need Staffing publiceert geen plaatsingsdatum; we laten die dus leeg
        # in plaats van de startdatum als publicatiedatum te misbruiken.
        gepubliceerd=None,
        segment=duur,
        extern_id=href.rsplit("/", 1)[-1],
    )


def haal_op(
    ophaler: Ophaler,
    voorselectie=None,
    max_details: int = 120,
    **_: object,
) -> list[PlatformResultaat]:
    uitvragen: dict[str, Uitvraag] = {}
    fout = ""
    try:
        for pagina in range(1, MAX_PAGINAS + 1):
            soep = ophaler.soep(LIJST.format(pagina=pagina))
            nieuw = 0
            for anker in soep.select('a[href^="/Opdrachten/"]'):
                uitvraag = _uit_kaart(anker)
                if uitvraag and uitvraag.extern_id not in uitvragen:
                    uitvragen[uitvraag.extern_id] = uitvraag
                    nieuw += 1
            if nieuw == 0:
                break
    except Exception as exc:  # noqa: BLE001
        fout = f"{type(exc).__name__}: {exc}"
        log.warning("Need Staffing ophalen mislukt: %s", fout)
        if not uitvragen:
            return [PlatformResultaat(platform="Need Staffing", gelukt=False, melding=fout)]

    regels = list(uitvragen.values())
    kandidaten = regels if voorselectie is None else [u for u in regels if voorselectie(u)]
    kandidaten, afgekapt = kies_details(kandidaten, max_details)
    opgehaald, mislukt, eerste_fout = 0, 0, ""
    for uitvraag in kandidaten:
        try:
            uitvraag.omschrijving = tekst_uit_html(ophaler.haal(uitvraag.url).text)
            opgehaald += 1
        except Exception as exc:  # noqa: BLE001
            mislukt += 1
            if not eerste_fout:
                eerste_fout = f"{type(exc).__name__}: {exc}"
            log.debug("Need Staffing detail mislukt voor %s: %s", uitvraag.url, exc)

    melding = fout or f"{opgehaald} omschrijvingen opgehaald"
    if mislukt:
        melding += f", {mislukt} mislukt ({eerste_fout})"
    if afgekapt:
        melding += f"; {afgekapt}"
    return [PlatformResultaat(platform="Need Staffing", uitvragen=regels, melding=melding)]
