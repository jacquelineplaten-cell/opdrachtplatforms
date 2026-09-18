"""Flextender.

Flextender is alleen met inlog te zien. Het inlogformulier op
https://app.flextender.nl/ post drie velden terug naar dezelfde URL:

    login[__config]   verborgen token dat per paginabezoek verschilt
    login[username]   e-mailadres
    login[password]   wachtwoord

Na het inloggen zoeken we de pagina met openstaande aanvragen. Omdat elk
Flextender-account een eigen inrichting heeft, is de lijstpagina in te stellen
met FLEXTENDER_LIST_URL; staat die niet ingesteld, dan zoeken we hem zelf op in
het menu. Zonder inloggegevens slaat deze scraper zichzelf netjes over.
"""

from __future__ import annotations

import logging
import os
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import PlatformResultaat, Uitvraag
from .base import Ophaler, tekst_uit_html

log = logging.getLogger(__name__)

BASIS = "https://app.flextender.nl/"
MENU_WOORDEN = ("aanvraag", "aanvragen", "opdracht", "opdrachten", "vacature", "marktplaats")
DETAIL_PATROON = re.compile(r"(aanvraag|opdracht|job|request)", re.IGNORECASE)


def _inloggen(ophaler: Ophaler, gebruiker: str, wachtwoord: str) -> BeautifulSoup:
    pagina = ophaler.soep(BASIS)
    token_veld = pagina.find("input", attrs={"name": "login[__config]"})
    if not token_veld:
        raise RuntimeError("inlogformulier niet herkend (geen login[__config] gevonden)")

    formulier = {
        "login[__config]": token_veld.get("value", ""),
        "login[username]": gebruiker,
        "login[password]": wachtwoord,
    }
    melding_veld = pagina.find("input", attrs={"name": "flxNotification[__config]"})
    if melding_veld:
        formulier["flxNotification[__config]"] = melding_veld.get("value", "")

    antwoord = ophaler.sessie.post(
        BASIS, data=formulier, timeout=ophaler.timeout, allow_redirects=True
    )
    antwoord.raise_for_status()
    na_inlog = BeautifulSoup(antwoord.text, "lxml")
    if na_inlog.find("input", attrs={"name": "login[password]"}):
        # Flextender toont bij een afwijzing geen foutmelding: je krijgt exact
        # dezelfde loginpagina terug. We kunnen dus niet zien wat er mis is en
        # noemen daarom de twee oorzaken die het in de praktijk zijn.
        raise RuntimeError(
            "inloggen geweigerd (Flextender geeft geen reden). Controleer "
            "FLEXTENDER_USERNAME en FLEXTENDER_PASSWORD, en of je account met "
            "e-mailadres en wachtwoord werkt: gaat je inlog via 'Log in met uw "
            "Microsoft account', dan werkt dit formulier niet"
        )
    return na_inlog


def _zoek_lijstpagina(ophaler: Ophaler, na_inlog: BeautifulSoup) -> str | None:
    for anker in na_inlog.find_all("a", href=True):
        label = " ".join(anker.get_text(" ").split()).lower()
        href = anker["href"]
        if any(woord in label for woord in MENU_WOORDEN) or any(
            woord in href.lower() for woord in MENU_WOORDEN
        ):
            return urljoin(BASIS, href)
    return None


def _uit_tabel(soep: BeautifulSoup, bron_url: str) -> list[Uitvraag]:
    uitvragen: dict[str, Uitvraag] = {}
    for anker in soep.find_all("a", href=True):
        href = anker["href"]
        if not DETAIL_PATROON.search(href):
            continue
        titel = " ".join(anker.get_text(" ").split())
        if len(titel) < 5:
            continue
        url = urljoin(bron_url, href)
        if url in uitvragen:
            continue

        rij = anker.find_parent("tr")
        context = " ".join(rij.get_text(" ").split()) if rij else titel
        uitvragen[url] = Uitvraag(
            platform="Flextender",
            titel=titel,
            url=url,
            omschrijving=context,
            extern_id=url,
        )
    return list(uitvragen.values())


def haal_op(ophaler: Ophaler, **_: object) -> list[PlatformResultaat]:
    gebruiker = os.environ.get("FLEXTENDER_USERNAME", "").strip()
    wachtwoord = os.environ.get("FLEXTENDER_PASSWORD", "").strip()
    if not gebruiker or not wachtwoord:
        return [
            PlatformResultaat(
                platform="Flextender",
                gelukt=False,
                melding=(
                    "overgeslagen: geen inloggegevens ingesteld "
                    "(secrets FLEXTENDER_USERNAME en FLEXTENDER_PASSWORD)"
                ),
            )
        ]

    try:
        na_inlog = _inloggen(ophaler, gebruiker, wachtwoord)
    except Exception as exc:  # noqa: BLE001
        return [
            PlatformResultaat(
                platform="Flextender", gelukt=False, melding=f"{type(exc).__name__}: {exc}"
            )
        ]

    lijst_url = os.environ.get("FLEXTENDER_LIST_URL", "").strip() or _zoek_lijstpagina(
        ophaler, na_inlog
    )
    if not lijst_url:
        return [
            PlatformResultaat(
                platform="Flextender",
                gelukt=False,
                melding=(
                    "ingelogd, maar de pagina met aanvragen niet gevonden. "
                    "Zet FLEXTENDER_LIST_URL op de URL die je na inloggen ziet."
                ),
            )
        ]

    try:
        soep = ophaler.soep(lijst_url)
    except Exception as exc:  # noqa: BLE001
        return [
            PlatformResultaat(
                platform="Flextender",
                gelukt=False,
                melding=f"lijstpagina {lijst_url} niet opgehaald: {type(exc).__name__}: {exc}",
            )
        ]

    uitvragen = _uit_tabel(soep, lijst_url)
    if not uitvragen:
        return [
            PlatformResultaat(
                platform="Flextender",
                gelukt=False,
                melding=(
                    f"ingelogd op {lijst_url}, maar geen aanvragen herkend. "
                    "De lijst wordt daar mogelijk met JavaScript geladen; "
                    "zet FLEXTENDER_LIST_URL op de juiste pagina."
                ),
            )
        ]

    for uitvraag in uitvragen:
        try:
            uitvraag.omschrijving = tekst_uit_html(ophaler.haal(uitvraag.url).text)
        except Exception as exc:  # noqa: BLE001
            log.debug("Flextender detail mislukt voor %s: %s", uitvraag.url, exc)

    return [PlatformResultaat(platform="Flextender", uitvragen=uitvragen)]
