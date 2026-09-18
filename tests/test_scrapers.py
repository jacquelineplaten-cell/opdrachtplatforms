"""Parsertests op echte, ingekorte antwoorden van de platforms."""

import json

from bs4 import BeautifulSoup

from opdrachtalert.scrapers import circle8, freep, needstaffing, striive
from opdrachtalert.scrapers.base import parse_datum, uren_tekst

from conftest import FIXTURES


def test_striive_leest_een_uitvraag():
    data = json.loads((FIXTURES / "striive_jobs.json").read_text(encoding="utf-8"))
    uitvragen = [striive._naar_uitvraag(j) for j in data["data"]]

    eerste = uitvragen[0]
    assert eerste.platform == striive.PLATFORM
    assert eerste.titel == "BI & Data Applications Developer"
    assert eerste.opdrachtgever == "Belastingdienst - ICT"
    assert eerste.bron == "Between"
    assert eerste.uren_per_week == "36"
    assert eerste.url.startswith("https://striive.com/nl/opdrachten?id=")
    assert "Opdrachtomschrijving" in eerste.omschrijving
    assert "<p>" not in eerste.omschrijving  # HTML is eruit gehaald
    assert eerste.gepubliceerd is not None


def test_needstaffing_leest_de_kaart():
    soep = BeautifulSoup((FIXTURES / "needstaffing_lijst.html").read_text(encoding="utf-8"), "lxml")
    uitvragen = [
        u
        for u in (needstaffing._uit_kaart(a) for a in soep.select('a[href^="/Opdrachten/"]'))
        if u
    ]
    assert len(uitvragen) == 2

    eerste = uitvragen[0]
    assert eerste.titel == "Infra Specialist (Cisco) 24835384"
    assert eerste.opdrachtgever == "Ministerie van Defensie"
    assert eerste.locatie == "Bernard Kazerne (1-2 dagen thuis)"
    assert eerste.uren_per_week == "32"
    assert eerste.tarief == "€70-82"
    assert eerste.sluitingsdatum.startswith("23-09-2026")
    # Need Staffing publiceert geen plaatsingsdatum, dus die hoort leeg te blijven.
    assert eerste.gepubliceerd is None
    assert eerste.url == "https://needstaffing.nl/Opdrachten/15605"


def test_freep_leest_de_samenvatting():
    data = json.loads((FIXTURES / "freep_assignments.json").read_text(encoding="utf-8"))
    eerste = freep._naar_uitvraag(data[0])
    assert eerste.platform == "Freep"
    assert eerste.url == "https://www.freep.nl/opdracht/" + data[0]["slug"]
    assert eerste.opdrachtgever == data[0]["company_name"]
    assert eerste.gepubliceerd is not None


def test_circle8_leest_jsonld():
    html = """
    <html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@type":"JobPosting",
     "title":"Innovatiemanager","url":"https://www.circle8.nl/opdracht/innovatiemanager",
     "description":"<p>Je versnelt innovatie bij een netbeheerder.</p>",
     "datePosted":"2026-09-10",
     "hiringOrganization":{"@type":"Organization","name":"Alliander"},
     "jobLocation":{"@type":"Place","address":{"addressLocality":"Arnhem"}}}
    </script></head><body></body></html>
    """
    uitvragen = circle8._uit_jsonld(BeautifulSoup(html, "lxml"))
    assert len(uitvragen) == 1
    assert uitvragen[0].titel == "Innovatiemanager"
    assert uitvragen[0].opdrachtgever == "Alliander"
    assert uitvragen[0].locatie == "Arnhem"
    assert uitvragen[0].omschrijving == "Je versnelt innovatie bij een netbeheerder."


def test_circle8_valt_terug_op_links():
    html = """
    <html><body>
      <a href="/opdracht/innovatieadviseur"><h3>Innovatieadviseur</h3><p>Utrecht, 32 uur</p></a>
      <a href="/over-ons">Over ons</a>
    </body></html>
    """
    uitvragen = circle8._uit_links(BeautifulSoup(html, "lxml"))
    assert [u.titel for u in uitvragen] == ["Innovatieadviseur"]
    assert uitvragen[0].url == "https://www.circle8.nl/opdracht/innovatieadviseur"


def test_circle8_herkent_een_blokkade():
    assert circle8._is_geblokkeerd("<html><title>Vercel Security Checkpoint</title>")
    assert circle8._is_geblokkeerd("<html><title>403: Forbidden</title>")
    assert not circle8._is_geblokkeerd("<html><title>Opdrachten</title>")


def test_datums_en_uren():
    assert parse_datum("2026-09-17T15:20:17") is not None
    assert parse_datum("17-09-2026") is not None
    assert parse_datum("2026-09-17T16:17:10.804766+02:00") is not None
    assert parse_datum("") is None
    assert parse_datum("onzin") is None

    assert uren_tekst(36, 36) == "36"
    assert uren_tekst(16, 24) == "16-24"
    assert uren_tekst(0, 0) is None
    assert uren_tekst(None, 32) == "32"


def test_dedup_voegt_hetzelfde_over_platforms_samen():
    from opdrachtalert.dedup import dedupliceer, titelsleutel
    from opdrachtalert.models import Uitvraag

    assert titelsleutel("BI & Data Applications Developer 2026-BZB-0474") == titelsleutel(
        "BI & Data Applications Developer"
    )
    assert titelsleutel("een Programmamanager Maatschappelijk Prioriteren") == titelsleutel(
        "Programmamanager maatschappelijk prioriteren"
    )

    uitvragen = [
        Uitvraag(platform="Freep", titel="Een programmamanager prioriteren", url="a",
                 opdrachtgever="Enexis", omschrijving="kort"),
        Uitvraag(platform="Striive", titel="Programmamanager prioriteren", url="b",
                 opdrachtgever="Enexis", omschrijving="een veel langere omschrijving" * 5),
        # Zelfde titel, andere opdrachtgever: dat zijn twee verschillende opdrachten.
        Uitvraag(platform="Freep", titel="Projectleider", url="c", opdrachtgever="Gemeente Breda"),
        Uitvraag(platform="Freep", titel="Projectleider", url="d", opdrachtgever="Gemeente Utrecht"),
    ]
    resultaat = dedupliceer(uitvragen)
    assert len(resultaat) == 3

    samengevoegd = next(u for u in resultaat if "prioriteren" in u.titel.lower())
    assert samengevoegd.platform == "Striive"  # de rijkste versie blijft staan
    assert samengevoegd.ook_op == ["Freep"]


def test_freep_detail_vult_de_omschrijving_aan():
    """De omschrijving komt van api.freep.nl, niet van de website.

    www.freep.nl weigert verzoeken vanaf datacenter-IP's; in GitHub Actions
    mislukten daardoor alle 112 detailpagina's en bleef de scoring steken op
    alleen de titel.
    """
    from opdrachtalert.scrapers import freep

    uitvraag = freep._naar_uitvraag(
        {"slug": "ucc-specialist-1", "title": "Ucc specialist", "hours": 32}
    )
    assert uitvraag.omschrijving == ""

    freep._vul_aan(
        uitvraag,
        {
            "content": "<p><strong>Opdrachtomschrijving</strong><br />Je werkt aan innovatie.</p>",
            "start_date": "2026-10-30",
            "closing_date": "2026-09-23T12:00:00+02:00",
            "location_name": "Den Haag",
            "rate_min": 90,
            "rate_max": 110,
        },
    )
    assert uitvraag.omschrijving == "Opdrachtomschrijving Je werkt aan innovatie."
    assert uitvraag.startdatum == "30-10-2026"
    assert uitvraag.sluitingsdatum == "23-09-2026"
    assert uitvraag.locatie == "Den Haag"
    assert uitvraag.tarief == "€90-110 p/u"
    # De detail-URL loopt over de API-host, de link in de mail naar de website.
    assert freep.DETAIL.startswith("https://api.freep.nl/")
    assert uitvraag.url.startswith("https://www.freep.nl/")


def test_freep_tarief_nul_is_geen_tarief():
    from opdrachtalert.scrapers import freep

    assert freep._tarief({"rate_min": 0, "rate_max": 0}) == ""
    assert freep._tarief({"rate_min": 0, "rate_max": 125}) == "max €125 p/u"


def test_flextender_leest_de_publieke_kaart():
    """Flextender komt van de openbare zoekresultaten, niet meer achter een inlog.

    Inloggen op app.flextender.nl werkte niet: bij een afwijzing geeft
    Flextender exact dezelfde loginpagina terug, zonder reden, en ook een echte
    browser kwam er niet doorheen. De opdrachtenpagina van www.flextender.nl
    levert dezelfde uitvragen publiek.
    """
    from opdrachtalert.scrapers import flextender

    soep = BeautifulSoup(
        (FIXTURES / "flextender_resultaten.html").read_text(encoding="utf-8"), "lxml"
    )
    uitvragen = [
        u for u in (flextender._uit_kaart(k) for k in soep.select(".css-foundjob")) if u
    ]
    assert len(uitvragen) == 2

    eerste = uitvragen[0]
    assert eerste.platform == "Flextender"
    assert eerste.titel == "Beleidsadviseur Ruimte"
    assert eerste.opdrachtgever == "Gemeente De Ronde Venen"
    assert eerste.locatie == "Utrecht"
    assert eerste.uren_per_week == "36"
    assert eerste.sluitingsdatum == "23-09-2026"
    # De URL wijst naar de publieke detailpagina, op aanvraagnummer.
    assert eerste.extern_id == "32543"
    assert eerste.url == "https://app.flextender.nl/nologin/jobdetails/32543"


def test_flextender_datum_en_uren():
    from opdrachtalert.scrapers import flextender

    assert flextender._nl_datum("23 september 2026 agenda") == "23-09-2026"
    assert flextender._nl_datum("1 maart 2027") == "01-03-2027"
    assert flextender._nl_datum("geen datum") == ""
    assert flextender._uren("36 uur") == "36"
    assert flextender._uren("16 - 24 uur") == "16-24"
    assert flextender._uren("in overleg") is None
