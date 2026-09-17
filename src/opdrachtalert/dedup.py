"""Dezelfde uitvraag samenvoegen als die op meerdere platforms staat.

Veel opdrachten worden door meerdere bemiddelaars uitgezet: dezelfde
programmamanager bij Enexis staat zowel op Freep als op Striive, en Need
Staffing plakt er nog een referentiecode achter. In de mail wil je die één keer
zien, met daarbij waar je nog meer kunt reageren.

We groeperen op de genormaliseerde titel en voegen alleen samen als de
opdrachtgevers elkaar niet tegenspreken.
"""

from __future__ import annotations

import re

from .matching import normaliseer
from .models import Uitvraag

LIDWOORDEN = ("een ", "de ", "het ")
# Referentiecodes als "2026-BZB-0474", "SRQ202007" of "24835384" horen niet bij
# de titel. We knippen ze weg vóór het normaliseren, anders blijft er van
# "2026-BZB-0474" een los "bzb" over dat de vergelijking alsnog laat mislukken.
REFERENTIE = re.compile(r"\S*\d\S*")


def titelsleutel(titel: str) -> str:
    zonder_codes = REFERENTIE.sub(" ", titel or "")
    tekst = normaliseer(zonder_codes)
    for lidwoord in LIDWOORDEN:
        if tekst.startswith(lidwoord):
            tekst = tekst[len(lidwoord):]
            break
    return " ".join(tekst.split())


def _klanten_botsen(links: str, rechts: str) -> bool:
    a, b = normaliseer(links), normaliseer(rechts)
    if not a or not b:
        return False
    return not (a in b or b in a)


def _rijkdom(uitvraag: Uitvraag) -> tuple[int, int]:
    """Welke versie tonen we? Die met de meeste informatie."""
    return (len(uitvraag.omschrijving), len(uitvraag.opdrachtgever))


def dedupliceer(uitvragen: list[Uitvraag]) -> list[Uitvraag]:
    groepen: dict[str, list[Uitvraag]] = {}
    for uitvraag in uitvragen:
        sleutel = titelsleutel(uitvraag.titel)
        if not sleutel:
            groepen[f"__leeg__{id(uitvraag)}"] = [uitvraag]
            continue
        groepen.setdefault(sleutel, []).append(uitvraag)

    resultaat: list[Uitvraag] = []
    for groep in groepen.values():
        resultaat.extend(_voeg_samen(groep))
    return resultaat


def _voeg_samen(groep: list[Uitvraag]) -> list[Uitvraag]:
    """Binnen één titel nog splitsen op opdrachtgevers die elkaar tegenspreken."""
    clusters: list[list[Uitvraag]] = []
    for uitvraag in groep:
        for cluster in clusters:
            if not any(_klanten_botsen(uitvraag.opdrachtgever, c.opdrachtgever) for c in cluster):
                cluster.append(uitvraag)
                break
        else:
            clusters.append([uitvraag])

    samengevoegd: list[Uitvraag] = []
    for cluster in clusters:
        beste = max(cluster, key=_rijkdom)
        andere = sorted(
            {u.platform for u in cluster if u.platform != beste.platform}
        )
        beste.ook_op = andere
        samengevoegd.append(beste)
    return samengevoegd
