"""Circle8.

Circle8 staat achter de botbescherming van Vercel: gewone HTTP-verzoeken vanaf
een datacenter-IP krijgen 403 of 429 terug. Daarom eerst een gewoon verzoek en
bij een blokkade een echte browser (Playwright/Chromium).

Het parsen gebeurt in twee stappen, van precies naar grof:
  1. JSON-LD JobPosting-blokken (die publiceren de meeste vacaturesites voor Google).
  2. De links naar detailpagina's plus de tekst van de kaart eromheen.

Lukt geen van beide, dan meldt deze scraper dat eerlijk en blijft de rest van
de alert gewoon werken.
"""

from __future__ import annotations

import json
import logging
import os
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import PlatformResultaat, Uitvraag
from .base import Ophaler, parse_datum, tekst_uit_html

log = logging.getLogger(__name__)

BASIS = "https://www.circle8.nl"
LIJST = BASIS + "/opdrachten"
DETAIL_PATROON = re.compile(r"^/opdracht(?:en)?/[^/?#]+/?$")
BLOKKADE = ("security checkpoint", "403: forbidden", "just a moment")


def _is_geblokkeerd(html: str) -> bool:
    kop = html[:4000].lower()
    return any(fragment in kop for fragment in BLOKKADE)


def _via_browser(url: str, laad_timeout: float, selector_timeout: float) -> str:
    """Rendert de pagina met de voorgeïnstalleerde Chromium van Playwright."""
    from playwright.sync_api import sync_playwright

    startargs = ["--no-sandbox", "--disable-dev-shm-usage"]
    # Alleen bedoeld voor een lokale sessie achter een TLS-onderscheppende proxy;
    # in GitHub Actions is deze variabele niet gezet.
    spki = os.environ.get("CHROMIUM_EXTRA_SPKI")
    if spki:
        startargs.append(f"--ignore-certificate-errors-spki-list={spki}")

    uitvoerbaar = os.environ.get("CHROMIUM_PATH")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=uitvoerbaar or None, args=startargs)
        try:
            pagina = browser.new_page(locale="nl-NL")
            pagina.goto(url, wait_until="domcontentloaded", timeout=laad_timeout * 1000)
            try:
                pagina.wait_for_selector("a[href*='opdracht']", timeout=selector_timeout * 1000)
            except Exception:  # noqa: BLE001 - dan pakken we wat er wél staat
                pagina.wait_for_timeout(5_000)
            return pagina.content()
        finally:
            browser.close()


def _uit_jsonld(soep: BeautifulSoup) -> list[Uitvraag]:
    uitvragen: list[Uitvraag] = []
    for blok in soep.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(blok.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for knoop in _platgeslagen(data):
            if str(knoop.get("@type", "")).lower() != "jobposting":
                continue
            werkgever = knoop.get("hiringOrganization") or {}
            uitvragen.append(
                Uitvraag(
                    platform="Circle8",
                    titel=str(knoop.get("title") or ""),
                    url=str(knoop.get("url") or LIJST),
                    opdrachtgever=str(
                        werkgever.get("name") if isinstance(werkgever, dict) else werkgever or ""
                    ),
                    omschrijving=tekst_uit_html(str(knoop.get("description") or "")),
                    locatie=_plaats(knoop.get("jobLocation")),
                    gepubliceerd=parse_datum(knoop.get("datePosted")),
                    extern_id=str(knoop.get("identifier") or knoop.get("url") or ""),
                )
            )
    return uitvragen


def _platgeslagen(data: object) -> list[dict]:
    if isinstance(data, dict):
        if "@graph" in data:
            return _platgeslagen(data["@graph"])
        return [data]
    if isinstance(data, list):
        uit: list[dict] = []
        for item in data:
            uit.extend(_platgeslagen(item))
        return uit
    return []


def _plaats(locatie: object) -> str:
    if isinstance(locatie, list):
        return ", ".join(filter(None, (_plaats(x) for x in locatie)))
    if isinstance(locatie, dict):
        adres = locatie.get("address")
        if isinstance(adres, dict):
            return str(adres.get("addressLocality") or adres.get("addressRegion") or "")
        return str(locatie.get("name") or "")
    return str(locatie or "")


def _uit_links(soep: BeautifulSoup) -> list[Uitvraag]:
    gezien: dict[str, Uitvraag] = {}
    for anker in soep.find_all("a", href=True):
        href = anker["href"]
        pad = href.replace(BASIS, "")
        if not DETAIL_PATROON.match(pad):
            continue
        url = urljoin(BASIS, href)
        if url in gezien:
            continue
        regels = [r.strip() for r in anker.get_text("\n").split("\n") if r.strip()]
        if not regels:
            continue
        gezien[url] = Uitvraag(
            platform="Circle8",
            titel=regels[0],
            url=url,
            omschrijving=" ".join(regels[1:]),
            extern_id=pad.strip("/"),
        )
    return list(gezien.values())


def haal_op(
    ophaler: Ophaler,
    platform_config: dict | None = None,
    **_: object,
) -> list[PlatformResultaat]:
    instellingen = platform_config or {}
    gebruik_browser = bool(instellingen.get("gebruik_browser", True))
    laad_timeout = float(instellingen.get("browser_laad_timeout_seconden", 60))
    selector_timeout = float(instellingen.get("browser_selector_timeout_seconden", 20))

    html = ""
    notities: list[str] = []
    try:
        html = ophaler.haal(LIJST).text
    except Exception as exc:  # noqa: BLE001
        notities.append(f"gewoon verzoek mislukt ({type(exc).__name__})")

    if (not html or _is_geblokkeerd(html)) and gebruik_browser:
        notities.append("botbescherming actief, browser geprobeerd")
        try:
            html = _via_browser(LIJST, laad_timeout, selector_timeout)
        except Exception as exc:  # noqa: BLE001
            return [
                PlatformResultaat(
                    platform="Circle8",
                    gelukt=False,
                    melding="; ".join(notities + [f"browser mislukt: {type(exc).__name__}: {exc}"]),
                )
            ]

    if not html or _is_geblokkeerd(html):
        return [
            PlatformResultaat(
                platform="Circle8",
                gelukt=False,
                melding="; ".join(notities + ["pagina bleef geblokkeerd"]),
            )
        ]

    soep = BeautifulSoup(html, "lxml")
    uitvragen = _uit_jsonld(soep) or _uit_links(soep)
    if not uitvragen:
        return [
            PlatformResultaat(
                platform="Circle8",
                gelukt=False,
                melding="; ".join(
                    notities + ["pagina opgehaald maar geen uitvragen herkend (opmaak gewijzigd?)"]
                ),
            )
        ]
    return [
        PlatformResultaat(platform="Circle8", uitvragen=uitvragen, melding="; ".join(notities))
    ]
