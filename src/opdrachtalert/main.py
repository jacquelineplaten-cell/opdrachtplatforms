"""Wekelijkse opdrachtalert: ophalen, scoren, mailen."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

import yaml

from .dedup import dedupliceer
from .mailer import MailInstellingen, bouw_bericht, verstuur
from .models import PlatformResultaat, Uitvraag
from .profielen import actieve_profielen, laad_profielen
from .render import maak_html, maak_tekst
from .scoring import beoordeel, beoordeel_alles
from .scrapers import SCRAPERS
from .scrapers.base import Ophaler
from .state import Geheugen

log = logging.getLogger("opdrachtalert")

WORTEL = Path(__file__).resolve().parents[2]


def _voorselectie_maker(profielen, instellingen: dict):
    """Bepaalt voor welke uitvragen we de omschrijving ophalen.

    Een lijstweergave geeft alleen titel, opdrachtgever en soms een segment. We
    scoren daar alvast op, en halen de detailpagina alleen op als die score met
    een goede omschrijving nog boven de drempel kan uitkomen. Uitvragen die ook
    met de beste omschrijving niet in de buurt komen, slaan we over; dat scheelt
    honderden verzoeken per week zonder dat we een match mislopen.
    """
    drempel = int(instellingen["drempel"])
    marge = float(instellingen.get("voorselectie_marge", 4))

    def kansrijk(uitvraag: Uitvraag) -> bool:
        return any(
            beoordeel(uitvraag, profiel, instellingen).score >= drempel - marge
            for profiel in profielen
        )

    return kansrijk


def verzamel(config: dict, profielen, alleen: list[str] | None = None) -> list[PlatformResultaat]:
    ophalen = config["ophalen"]
    ophaler = Ophaler(
        timeout=int(ophalen["timeout_seconden"]),
        pauze=float(ophalen["pauze_tussen_verzoeken"]),
    )
    voorselectie = _voorselectie_maker(profielen, config["scoring"])

    resultaten: list[PlatformResultaat] = []
    for sleutel, functie in SCRAPERS.items():
        if alleen and sleutel not in alleen:
            continue
        if not config["platforms"].get(sleutel, {}).get("actief", True):
            log.info("Platform %s staat uit in config.yaml", sleutel)
            continue
        log.info("Ophalen: %s", sleutel)
        try:
            resultaten.extend(
                functie(
                    ophaler,
                    voorselectie=voorselectie,
                    max_details=int(ophalen["max_details_per_platform"]),
                )
            )
        except Exception as exc:  # noqa: BLE001 - nooit de hele alert laten vallen
            log.exception("Scraper %s crashte", sleutel)
            resultaten.append(
                PlatformResultaat(
                    platform=sleutel, gelukt=False, melding=f"{type(exc).__name__}: {exc}"
                )
            )
    return resultaten


def _bewaar_ruw(resultaten: list[PlatformResultaat], pad: Path) -> None:
    """De onbewerkte oogst wegschrijven, om later te kunnen herscoren zonder ophalen."""
    data = [
        {
            "platform": r.platform,
            "gelukt": r.gelukt,
            "melding": r.melding,
            "uitvragen": [_als_dict(u) for u in r.uitvragen],
        }
        for r in resultaten
    ]
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Ruwe oogst weggeschreven naar %s", pad)


def _als_dict(uitvraag: Uitvraag) -> dict:
    regel = asdict(uitvraag)
    regel["gepubliceerd"] = uitvraag.gepubliceerd.isoformat() if uitvraag.gepubliceerd else None
    return regel


def _lees_ruw(pad: Path) -> list[PlatformResultaat]:
    data = json.loads(pad.read_text(encoding="utf-8"))
    resultaten = []
    for blok in data:
        uitvragen = []
        for regel in blok["uitvragen"]:
            regel = dict(regel)
            stempel = regel.pop("gepubliceerd", None)
            uitvraag = Uitvraag(**regel)
            uitvraag.gepubliceerd = date.fromisoformat(stempel) if stempel else None
            uitvragen.append(uitvraag)
        resultaten.append(
            PlatformResultaat(
                platform=blok["platform"],
                uitvragen=uitvragen,
                gelukt=blok.get("gelukt", True),
                melding=blok.get("melding", ""),
            )
        )
    log.info("Ruwe oogst gelezen uit %s", pad)
    return resultaten


def _filter_op_leeftijd(uitvragen: list[Uitvraag], max_dagen: int) -> list[Uitvraag]:
    if max_dagen <= 0:
        return uitvragen
    bewaard = []
    for uitvraag in uitvragen:
        leeftijd = uitvraag.leeftijd_dagen
        if leeftijd is None or leeftijd <= max_dagen:
            bewaard.append(uitvraag)
    return bewaard


def draai(args: argparse.Namespace) -> int:
    config = yaml.safe_load((WORTEL / "config.yaml").read_text(encoding="utf-8"))
    alle_profielen = laad_profielen(WORTEL / "profiles.yaml")
    profielen = actieve_profielen(alle_profielen)
    if not profielen:
        log.error("Geen actieve profielen met inhoud in profiles.yaml")
        return 1

    overgeslagen = [p.naam for p in alle_profielen if p not in profielen]
    if overgeslagen:
        log.info("Overgeslagen profielen (inactief of leeg): %s", ", ".join(overgeslagen))

    if args.drempel is not None:
        config["scoring"]["drempel"] = args.drempel

    if args.lees_ruwe:
        resultaten = _lees_ruw(Path(args.lees_ruwe))
    else:
        resultaten = verzamel(config, profielen, alleen=args.platform or None)
    if args.bewaar_ruwe:
        _bewaar_ruw(resultaten, Path(args.bewaar_ruwe))

    uitvragen = [u for r in resultaten for u in r.uitvragen]
    uitvragen = _filter_op_leeftijd(uitvragen, int(config["ophalen"]["max_leeftijd_dagen"]))
    voor_dedup = len(uitvragen)
    uitvragen = dedupliceer(uitvragen)
    log.info(
        "Totaal %d uitvragen na leeftijdsfilter, %d na samenvoegen van dubbelen",
        voor_dedup,
        len(uitvragen),
    )

    if args.diagnose:
        return _diagnose(args.diagnose, uitvragen, profielen, config["scoring"])

    per_persoon = beoordeel_alles(uitvragen, profielen, config["scoring"])

    geheugen = Geheugen(WORTEL / "state" / "gezien.json")
    getoond = {b.uitvraag.sleutel for lijst in per_persoon.values() for b in lijst}
    nieuw = {sleutel for sleutel in getoond if geheugen.is_nieuw(sleutel)}

    vandaag = date.today()
    html = maak_html(
        per_persoon,
        resultaten,
        nieuw,
        config["scoring"]["drempel"],
        vandaag,
        len(uitvragen),
    )
    tekst = maak_tekst(
        per_persoon,
        resultaten,
        nieuw,
        config["scoring"]["drempel"],
        vandaag,
        len(uitvragen),
    )
    onderwerp = config["mail"]["onderwerp"].format(
        week=vandaag.isocalendar().week, datum=vandaag.strftime("%d-%m-%Y")
    )

    if args.uitvoer:
        pad = Path(args.uitvoer)
        pad.parent.mkdir(parents=True, exist_ok=True)
        pad.write_text(html, encoding="utf-8")
        log.info("HTML weggeschreven naar %s", pad)

    if args.droogloop:
        print(tekst)
        log.info("Droogloop: geen mail verstuurd, geheugen niet bijgewerkt.")
        return 0

    if geheugen.al_verstuurd_deze_week(vandaag) and not args.forceer:
        log.info(
            "Deze week is al een alert verstuurd (%s). Niets gedaan. "
            "Gebruik --forceer om toch te versturen.",
            geheugen.laatste_verzending,
        )
        return 0

    instellingen = MailInstellingen()
    if not instellingen.compleet:
        log.error(
            "Mail niet verstuurd, ontbrekende instellingen: %s",
            ", ".join(instellingen.ontbrekend()),
        )
        return 2

    verstuur(instellingen, bouw_bericht(instellingen, onderwerp, tekst, html))
    geheugen.noteer(sorted(getoond), vandaag)
    geheugen.noteer_verzending(vandaag)
    geheugen.opschonen(vandaag=vandaag)
    geheugen.opslaan()
    return 0


def _diagnose(naam: str, uitvragen, profielen, instellingen: dict) -> int:
    """Toont de hoogst scorende uitvragen voor één persoon, ook onder de drempel.

    Handig als iemand week na week niets krijgt: zie je scores van 5 en 6, dan is
    het aanbod er wel maar net niet raak en kun je trefwoorden bijstellen. Blijft
    alles op 1 of 2 steken, dan staat er niets bruikbaars tussen.
    """
    gekozen = next((p for p in profielen if p.naam.lower() == naam.lower()), None)
    if not gekozen:
        log.error("Onbekende of inactieve persoon: %s. Bekend: %s",
                  naam, ", ".join(p.naam for p in profielen))
        return 1

    beoordelingen = sorted(
        (beoordeel(u, gekozen, instellingen) for u in uitvragen),
        key=lambda b: -b.score,
    )
    drempel = instellingen["drempel"]
    print(f"Top 25 voor {gekozen.naam} (drempel {drempel}), van {len(uitvragen)} uitvragen:\n")
    for beoordeling in beoordelingen[:25]:
        punten = " ".join(f"{k}={v:+.1f}" for k, v in beoordeling.onderdelen.items() if v)
        merk = "  " if beoordeling.score >= drempel else "· "
        print(f"{merk}{beoordeling.score:2}/10  {beoordeling.uitvraag.titel[:62]}")
        print(f"       {beoordeling.uitvraag.platform} | {beoordeling.uitvraag.opdrachtgever[:40]}")
        print(f"       {punten}")
        print(f"       {beoordeling.toelichting}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wekelijkse opdrachtalert innovatiegroep")
    parser.add_argument(
        "--droogloop",
        action="store_true",
        help="alles ophalen en scoren, maar niets mailen en niets onthouden",
    )
    parser.add_argument("--uitvoer", help="pad om de HTML-mail naar weg te schrijven")
    parser.add_argument(
        "--platform",
        action="append",
        choices=sorted(SCRAPERS),
        help="beperk tot dit platform (mag meerdere keren)",
    )
    parser.add_argument("--drempel", type=int, help="overschrijf de drempelscore uit config.yaml")
    parser.add_argument(
        "--bewaar-ruwe",
        dest="bewaar_ruwe",
        help="schrijf de opgehaalde uitvragen naar dit JSON-bestand",
    )
    parser.add_argument(
        "--lees-ruwe",
        dest="lees_ruwe",
        help="scoor opnieuw vanuit een eerder bewaard JSON-bestand, zonder op te halen",
    )
    parser.add_argument(
        "--forceer",
        action="store_true",
        help="ook versturen als er deze week al een alert uitging",
    )
    parser.add_argument(
        "--diagnose",
        metavar="NAAM",
        help="toon de 25 hoogste scores voor deze persoon, ook onder de drempel",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    return draai(args)


if __name__ == "__main__":
    raise SystemExit(main())
