"""Regelgebaseerde relevantiescore (1-10) van een uitvraag voor één persoon.

De score is opgebouwd uit vier plussen en één min:

  rol        functietitel uit het profiel, zwaar als die in de titel staat
  sector     opdrachtgever of markt uit het profiel
  expertise  vakinhoud, methoden en thema's uit het profiel
  kern       innovatiesignalen die voor de hele groep gelden
  boost      persoonlijke extra's (bv. "alle onderwijsuitvragen")
  straf      uitvoerende ICT-/specialistenrollen die geen innovatieadvies zijn

Elke categorie heeft een maximum, zodat een lange vacaturetekst niet vanzelf
hoog scoort. Het totaal wordt afgerond en begrensd op 1 tot en met 10.

Daarbovenop staat de innovatiepoort: past de functietitel en de sector wel, maar
gaat de uitvraag nergens over vernieuwen, dan blijft de score onder de drempel.
Een persoonlijke boost omzeilt die poort, zodat een expliciete wens ("laat mij
alle onderwijsuitvragen zien") altijd doorkomt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .matching import gevonden_termen, normaliseer
from .models import Uitvraag
from .profielen import Profiel


@dataclass
class Beoordeling:
    persoon: str
    uitvraag: Uitvraag
    score: int
    onderdelen: dict[str, float] = field(default_factory=dict)
    redenen: list[str] = field(default_factory=list)

    @property
    def toelichting(self) -> str:
        return "; ".join(self.redenen[:3]) if self.redenen else "geen expliciete match"


def _begrens(waarde: float, maximum: float) -> float:
    return min(waarde, maximum)


def beoordeel(
    uitvraag: Uitvraag,
    profiel: Profiel,
    instellingen: dict,
) -> Beoordeling:
    gewichten = instellingen["gewichten"]
    maxima = instellingen["maxima"]

    titel = normaliseer(uitvraag.titel)
    opdrachtgever = normaliseer(f"{uitvraag.opdrachtgever} {uitvraag.segment}")
    volledig = normaliseer(uitvraag.zoektekst)

    onderdelen: dict[str, float] = {}
    redenen: list[str] = []

    # --- rol -------------------------------------------------------------
    rollen_titel = gevonden_termen(titel, profiel.rollen)
    rollen_tekst = [r for r in gevonden_termen(volledig, profiel.rollen) if r not in rollen_titel]
    rol_punten = _begrens(
        len(rollen_titel) * gewichten["rol_in_titel"]
        + len(rollen_tekst) * gewichten["rol_in_tekst"],
        maxima["rol"],
    )
    onderdelen["rol"] = rol_punten
    if rollen_titel:
        redenen.append("rol in titel: " + ", ".join(rollen_titel[:3]))
    elif rollen_tekst:
        redenen.append("rol genoemd: " + ", ".join(rollen_tekst[:3]))

    # --- sector ----------------------------------------------------------
    sectoren_klant = gevonden_termen(opdrachtgever, profiel.sectoren)
    sectoren_tekst = [
        s for s in gevonden_termen(volledig, profiel.sectoren) if s not in sectoren_klant
    ]
    sector_punten = _begrens(
        len(sectoren_klant) * gewichten["sector_in_opdrachtgever"]
        + len(sectoren_tekst) * gewichten["sector_in_tekst"],
        maxima["sector"],
    )
    onderdelen["sector"] = sector_punten
    if sectoren_klant:
        redenen.append("sector: " + ", ".join(sectoren_klant[:3]))
    elif sectoren_tekst:
        redenen.append("sector genoemd: " + ", ".join(sectoren_tekst[:3]))

    # --- expertise -------------------------------------------------------
    expertise_titel = gevonden_termen(titel, profiel.expertise)
    expertise_tekst = [
        e for e in gevonden_termen(volledig, profiel.expertise) if e not in expertise_titel
    ]
    expertise_punten = _begrens(
        len(expertise_titel) * gewichten["expertise_in_titel"]
        + len(expertise_tekst) * gewichten["expertise_in_tekst"],
        maxima["expertise"],
    )
    onderdelen["expertise"] = expertise_punten
    getoonde_expertise = (expertise_titel + expertise_tekst)[:4]
    if getoonde_expertise:
        redenen.append("expertise: " + ", ".join(getoonde_expertise))

    # --- kern (geldt voor de hele groep) ---------------------------------
    kern_termen = instellingen["kern_termen"]
    kern_titel = gevonden_termen(titel, kern_termen)
    kern_tekst = [k for k in gevonden_termen(volledig, kern_termen) if k not in kern_titel]
    kern_punten = _begrens(
        len(kern_titel) * gewichten["kern_in_titel"] + len(kern_tekst) * gewichten["kern_in_tekst"],
        maxima["kern"],
    )
    onderdelen["kern"] = kern_punten

    # --- persoonlijke boost ----------------------------------------------
    # Een boost telt pas vol als hij op de opdrachtgever slaat. Staat het woord
    # alleen ergens in de omschrijving ("we werken ook met het onderwijs"), dan
    # telt hij maar voor een deel mee; anders sleept elke terloopse vermelding
    # een uitvraag de mail in.
    deel_in_tekst = float(gewichten.get("boost_in_tekst_aandeel", 0.4))
    boost_punten = 0.0
    volle_boost = False
    geraakte_boosts: list[str] = []
    for term, punten in profiel.boost.items():
        if gevonden_termen(opdrachtgever, [term]):
            boost_punten += punten
            volle_boost = True
            geraakte_boosts.append(term)
        elif gevonden_termen(volledig, [term]):
            boost_punten += punten * deel_in_tekst
            geraakte_boosts.append(f"{term} (genoemd)")
    boost_punten = _begrens(boost_punten, maxima["boost"])
    onderdelen["boost"] = boost_punten
    if geraakte_boosts:
        redenen.append("eigen voorkeur: " + ", ".join(sorted(set(geraakte_boosts))[:3]))

    # --- straf voor uitvoerende rollen -----------------------------------
    eigen_termen = {
        t.lower() for t in (profiel.rollen + profiel.expertise + profiel.sectoren)
    }
    kandidaten = [
        t for t in instellingen["uitsluit_termen"] + profiel.uitsluiten
        if t.lower() not in eigen_termen
    ]
    # Alleen de titel telt voor de straf: een omschrijving noemt vaak terloops
    # een developer of tester zonder dat de opdracht dat is.
    geraakt = gevonden_termen(titel, kandidaten)
    straf = min(len(geraakt), 2) * instellingen["uitsluit_straf"]
    onderdelen["straf"] = -straf
    if geraakt:
        redenen.append("uitvoerende rol in titel: " + ", ".join(geraakt[:2]))

    totaal = (
        rol_punten + sector_punten + expertise_punten + kern_punten + boost_punten - straf
    )
    score = int(max(1, min(10, round(totaal))))

    # --- innovatiepoort ---------------------------------------------------
    # Alleen een boost op de opdrachtgever zelf omzeilt de poort; een terloopse
    # vermelding in de omschrijving is geen expliciete wens.
    poort = instellingen.get("innovatie_poort") or {}
    if poort.get("actief") and not volle_boost:
        sterk = gevonden_termen(volledig, poort.get("sterke_termen", []))
        if not sterk:
            # Een cap op of boven de drempel zou de poort betekenisloos maken:
            # de uitvraag komt dan alsnog in de mail. Daarom hier begrensd.
            cap = min(
                int(poort.get("cap_zonder_signaal", 6)),
                int(instellingen["drempel"]) - 1,
            )
            if score > cap:
                score = cap
                redenen.append("geen vernieuwingssignaal in de uitvraag")

    return Beoordeling(
        persoon=profiel.naam,
        uitvraag=uitvraag,
        score=score,
        onderdelen=onderdelen,
        redenen=redenen,
    )


def beoordeel_alles(
    uitvragen: list[Uitvraag],
    profielen: list[Profiel],
    instellingen: dict,
) -> dict[str, list[Beoordeling]]:
    """Per persoon de beoordelingen boven de drempel, hoogste score eerst."""
    drempel = instellingen["drempel"]
    maximum = instellingen["max_per_persoon"]

    resultaat: dict[str, list[Beoordeling]] = {}
    for profiel in profielen:
        treffers = [beoordeel(u, profiel, instellingen) for u in uitvragen]
        relevant = [b for b in treffers if b.score >= drempel]
        relevant.sort(key=lambda b: (-b.score, b.uitvraag.titel.lower()))
        resultaat[profiel.naam] = relevant[:maximum]
    return resultaat
