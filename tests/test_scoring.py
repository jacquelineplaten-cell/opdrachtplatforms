import yaml
import pytest

from opdrachtalert.models import Uitvraag
from opdrachtalert.profielen import Profiel, actieve_profielen, laad_profielen
from opdrachtalert.scoring import beoordeel, beoordeel_alles

from conftest import WORTEL


@pytest.fixture(scope="module")
def instellingen():
    return yaml.safe_load((WORTEL / "config.yaml").read_text(encoding="utf-8"))["scoring"]


@pytest.fixture(scope="module")
def profielen():
    return {p.naam: p for p in laad_profielen(WORTEL / "profiles.yaml")}


def uitvraag(titel, opdrachtgever="", omschrijving=""):
    return Uitvraag(
        platform="Test",
        titel=titel,
        url="https://voorbeeld.nl/1",
        opdrachtgever=opdrachtgever,
        omschrijving=omschrijving,
    )


def test_kernopdracht_scoort_hoog_voor_de_juiste_persoon(instellingen, profielen):
    u = uitvraag(
        "Innovatiemanager operationele transformatie",
        "Ministerie van Defensie",
        "Je brengt prototypes naar de operationele eenheid, richt governance in en "
        "stuurt op adoptie en opschaling binnen het programma.",
    )
    assert beoordeel(u, profielen["Roderik"], instellingen).score >= 8


def test_uitvoerende_ict_rol_zakt_onder_de_drempel(instellingen, profielen):
    u = uitvraag(
        "Full Stack Developer Java / Angular",
        "Centraal Justitieel Incassobureau (CJIB)",
        "Je bouwt microservices en werkt in een agile team aan vernieuwing van de keten.",
    )
    for naam in ("Roderik", "Raben", "Vis"):
        assert beoordeel(u, profielen[naam], instellingen).score < instellingen["drempel"]


def test_sector_alleen_is_niet_genoeg(instellingen, profielen):
    u = uitvraag("Medewerker burgerzaken", "Gemeente Utrecht", "Je helpt inwoners aan de balie.")
    assert beoordeel(u, profielen["Mysia"], instellingen).score < instellingen["drempel"]


def test_onderwijsboost_werkt_voor_bellen(instellingen, profielen):
    u = uitvraag(
        "Projectleider onderwijsvernieuwing",
        "Hogeschool Rotterdam",
        "Je begeleidt een traject rond curriculum en organisatieontwikkeling.",
    )
    bellen = beoordeel(u, profielen["Bellen"], instellingen).score
    mysia = beoordeel(u, profielen["Mysia"], instellingen).score
    assert bellen >= 8
    assert bellen > mysia


def test_score_blijft_tussen_1_en_10(instellingen, profielen):
    veel = uitvraag(
        "Programmamanager innovatie en strategie",
        "Ministerie van Defensie",
        " ".join(["innovatie strategie transformatie kwartiermaker governance"] * 50),
    )
    niets = uitvraag("", "", "")
    for profiel in profielen.values():
        assert 1 <= beoordeel(veel, profiel, instellingen).score <= 10
        assert 1 <= beoordeel(niets, profiel, instellingen).score <= 10


def test_beoordeel_alles_respecteert_drempel_en_maximum(instellingen, profielen):
    instellingen = dict(instellingen, drempel=1, max_per_persoon=2)
    uitvragen = [uitvraag(f"Innovatiemanager {i}", "Gemeente Amsterdam") for i in range(5)]
    per_persoon = beoordeel_alles(uitvragen, actieve_profielen(list(profielen.values())), instellingen)
    assert all(len(v) <= 2 for v in per_persoon.values())
    assert all(b.score >= 1 for lijst in per_persoon.values() for b in lijst)


def test_leeg_profiel_telt_niet_mee():
    profielen = [
        Profiel(naam="Leeg", actief=True),
        Profiel(naam="Uit", actief=False, rollen=["projectleider"]),
        Profiel(naam="Goed", actief=True, rollen=["projectleider"]),
    ]
    assert [p.naam for p in actieve_profielen(profielen)] == ["Goed"]


def test_innovatiepoort_houdt_gewone_klussen_onder_de_drempel(instellingen, profielen):
    """Titel en sector passen, maar er zit geen vernieuwing in: dan geen mail."""
    u = uitvraag(
        "Projectleider vervanging riolering",
        "Gemeente Elburg",
        "Je stuurt de aannemer aan, bewaakt de planning, het budget en de "
        "besluitvorming in de stuurgroep en houdt de omwonenden op de hoogte.",
    )
    zonder_poort = dict(instellingen, innovatie_poort={"actief": False})
    met_poort = instellingen

    assert beoordeel(u, profielen["Mysia"], met_poort).score <= met_poort["innovatie_poort"][
        "cap_zonder_signaal"
    ]
    assert (
        beoordeel(u, profielen["Mysia"], zonder_poort).score
        >= beoordeel(u, profielen["Mysia"], met_poort).score
    )


def test_innovatiepoort_laat_vernieuwing_door(instellingen, profielen):
    u = uitvraag(
        "Projectleider woningbouwopgave",
        "Gemeente Elburg",
        "Je werkt aan de transformatie van de woningbouwopgave en zet een "
        "vernieuwende aanpak op met co-creatie tussen corporaties en ontwikkelaars.",
    )
    assert beoordeel(u, profielen["Mysia"], instellingen).score >= instellingen["drempel"]


def test_persoonlijke_boost_omzeilt_de_poort(instellingen, profielen):
    """Bellen wil alle onderwijsuitvragen zien, ook zonder vernieuwingssignaal."""
    u = uitvraag(
        "Projectleider roosterproces",
        "ROC Midden Nederland",
        "Je stuurt het roosterproces aan en stemt af met de opleidingsmanagers.",
    )
    assert beoordeel(u, profielen["Bellen"], instellingen).score >= instellingen["drempel"]


def test_generieke_klus_verdeelt_zich_niet_over_het_hele_team(instellingen, profielen):
    """Rol en sector delen ze; alleen expertise mag iemand boven de drempel tillen."""
    u = uitvraag(
        "Kwartiermaker financieel beheer",
        "Gemeente Pijnacker",
        "Je richt de financiële functie opnieuw in, werkt aan organisatieontwikkeling "
        "en professionalisering van het team en verbetert de dienstverlening.",
    )
    actief = [p for p in profielen.values() if p.actief and p.heeft_inhoud]
    boven = [p.naam for p in actief if beoordeel(u, p, instellingen).score >= instellingen["drempel"]]
    # Zonder weging op expertise haalde deze klus zeven van de tien profielen.
    assert len(boven) <= 4, f"te breed: {boven}"


def test_ondersteunende_functie_valt_af(instellingen, profielen):
    u = uitvraag(
        "Adviseur-senior administratief ondersteuner reorganisatie",
        "Hogeschool Utrecht",
        "Je ondersteunt de reorganisatie administratief en verzorgt de verslaglegging.",
    )
    # Ook met de onderwijsboost van Bellen hoort dit er niet in.
    assert beoordeel(u, profielen["Bellen"], instellingen).score < instellingen["drempel"]


def test_boost_telt_alleen_vol_bij_de_opdrachtgever(instellingen, profielen):
    """Een terloopse vermelding van onderwijs mag geen gemeenteklus binnenslepen."""
    bij_onderwijs = uitvraag(
        "Projectleider roosterproces",
        "ROC Midden Nederland",
        "Je stuurt het roosterproces aan.",
    )
    terloops = uitvraag(
        "Projectleider ondergrondse infrastructuur",
        "Enexis",
        "We werken samen met partners uit het onderwijs aan voldoende technici.",
    )
    assert beoordeel(bij_onderwijs, profielen["Bellen"], instellingen).score >= instellingen["drempel"]
    assert beoordeel(terloops, profielen["Bellen"], instellingen).score < instellingen["drempel"]
