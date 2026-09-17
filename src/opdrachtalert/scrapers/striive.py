"""Between en HeadFirst.

Beide sites draaien op het Striive-platform en delen één publieke API:

    GET https://striive-cms.codebridge.nl/api/jobs?open=true&page=N
        -> {"total": <int>, "data": [ ... 25 uitvragen ... ]}

Het veld ``source`` zegt van welk merk een uitvraag komt (HeadFirst, Between,
StarApple), dus we halen de lijst één keer op en splitsen hem daarna.
"""

from __future__ import annotations

import logging

from ..models import PlatformResultaat, Uitvraag
from .base import Ophaler, parse_datum, tekst_uit_html, uren_tekst

log = logging.getLogger(__name__)

API = "https://striive-cms.codebridge.nl/api/jobs"
PAGINAGROOTTE = 25
MAX_PAGINAS = 40

# between.com/opdrachten en headfirst.nl/opdrachten tonen allebei exact dezelfde
# Striive-lijst, dus we halen hem één keer op en rapporteren hem als één platform.
# Het veld "source" zegt onder welk merk je kunt reageren; dat zetten we per uitvraag.
PLATFORM = "Between / HeadFirst (Striive)"


def _naar_uitvraag(job: dict) -> Uitvraag:
    uuid = str(job.get("id") or "")
    return Uitvraag(
        platform=PLATFORM,
        bron=str(job.get("source") or "").strip(),
        titel=str(job.get("title") or ""),
        url=str(job.get("brokerUrl") or f"https://striive.com/nl/opdrachten?id={uuid}"),
        opdrachtgever=str(job.get("clientName") or ""),
        omschrijving=tekst_uit_html(str(job.get("content") or "")),
        locatie=str(job.get("location") or ""),
        uren_per_week=uren_tekst(job.get("hoursPerWeekMin"), job.get("hoursPerWeekMax")),
        tarief=_tarief(job),
        startdatum=_datum_tekst(job.get("startDate")),
        einddatum=_datum_tekst(job.get("endDate")),
        sluitingsdatum=_datum_tekst(job.get("closingDateInvoice") or job.get("closingDateClient")),
        gepubliceerd=parse_datum(job.get("publishedDate") or job.get("createdAt")),
        segment=str(job.get("segmentName") or ""),
        extern_id=uuid,
    )


def _tarief(job: dict) -> str:
    lo, hi = job.get("hourlyRateMin") or 0, job.get("hourlyRateMax") or 0
    if lo and hi and lo != hi:
        return f"€{lo}-{hi} p/u"
    if lo or hi:
        return f"€{lo or hi} p/u"
    return ""


def _datum_tekst(waarde: object) -> str:
    datum = parse_datum(waarde if isinstance(waarde, str) else None)
    return datum.strftime("%d-%m-%Y") if datum else ""


def haal_op(ophaler: Ophaler, **_: object) -> list[PlatformResultaat]:
    """Alle open uitvragen op Striive, als één platformresultaat."""
    uitvragen: list[Uitvraag] = []
    fout = ""
    try:
        pagina = 1
        totaal = None
        while pagina <= MAX_PAGINAS:
            data = ophaler.json(f"{API}?open=true&page={pagina}")
            if not isinstance(data, dict):
                break
            regels = data.get("data") or []
            if totaal is None:
                totaal = int(data.get("total") or 0)
            uitvragen.extend(_naar_uitvraag(j) for j in regels)
            if len(regels) < PAGINAGROOTTE or len(uitvragen) >= (totaal or 0):
                break
            pagina += 1
    except Exception as exc:  # noqa: BLE001 - één platform mag de rest niet slopen
        fout = f"{type(exc).__name__}: {exc}"
        log.warning("Striive ophalen mislukt: %s", fout)

    merken = sorted({u.bron for u in uitvragen if u.bron})
    melding = fout or (f"merken: {', '.join(merken)}" if merken else "")
    return [
        PlatformResultaat(
            platform=PLATFORM,
            uitvragen=uitvragen,
            gelukt=not fout,
            melding=melding,
        )
    ]
