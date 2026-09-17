"""Opmaak van de wekelijkse e-mail (HTML en platte tekst)."""

from __future__ import annotations

from datetime import date
from html import escape

from .models import PlatformResultaat
from .scoring import Beoordeling

KLEUREN = {
    10: "#14532d",
    9: "#166534",
    8: "#15803d",
    7: "#b45309",
}
GRIJS = "#4b5563"
RAND = "#e5e7eb"


def _badge_kleur(score: int) -> str:
    return KLEUREN.get(score, GRIJS)


def _feiten(beoordeling: Beoordeling) -> list[str]:
    u = beoordeling.uitvraag
    onderdelen = [f"{u.platform} - {u.bron}" if u.bron else u.platform]
    if u.opdrachtgever:
        onderdelen.append(u.opdrachtgever)
    if u.locatie:
        onderdelen.append(u.locatie)
    if u.uren_per_week:
        onderdelen.append(f"{u.uren_per_week} uur p/w")
    if u.tarief:
        onderdelen.append(u.tarief)
    if u.sluitingsdatum:
        onderdelen.append(f"sluit {u.sluitingsdatum}")
    elif u.startdatum:
        onderdelen.append(f"start {u.startdatum}")
    if u.ook_op:
        onderdelen.append("staat ook op " + ", ".join(u.ook_op))
    return onderdelen


def _fragment(tekst: str, lengte: int = 240) -> str:
    if len(tekst) <= lengte:
        return tekst
    return tekst[:lengte].rsplit(" ", 1)[0] + "..."


def maak_html(
    per_persoon: dict[str, list[Beoordeling]],
    platformstatus: list[PlatformResultaat],
    nieuw: set[str],
    drempel: int,
    vandaag: date,
    totaal_uitvragen: int,
) -> str:
    week = vandaag.isocalendar().week
    aantal_treffers = sum(len(v) for v in per_persoon.values())
    personen_met_werk = [n for n, v in per_persoon.items() if v]

    regels = [
        "<div style=\"font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
        "font-size:15px;line-height:1.5;color:#111827;max-width:720px;margin:0 auto;"
        "padding:8px 16px 32px;\">",
        f"<h1 style=\"font-size:20px;margin:16px 0 4px;\">Opdrachtalert innovatiegroep"
        f" &middot; week {week}</h1>",
        f"<p style=\"margin:0 0 20px;color:{GRIJS};font-size:13px;\">"
        f"{vandaag.strftime('%d-%m-%Y')} &middot; {totaal_uitvragen} uitvragen bekeken &middot; "
        f"{aantal_treffers} match{'es' if aantal_treffers != 1 else ''} met score {drempel} of hoger "
        f"voor {len(personen_met_werk)} van de {len(per_persoon)} teamleden</p>",
    ]

    if not aantal_treffers:
        regels.append(
            f"<p style=\"padding:16px;background:#fef3c7;border-radius:8px;\">"
            f"Deze week geen uitvragen met score {drempel} of hoger. "
            f"De platformstatus hieronder laat zien of dat aan het aanbod ligt "
            f"of aan een platform dat niet bereikbaar was.</p>"
        )

    for persoon, beoordelingen in per_persoon.items():
        if not beoordelingen:
            continue
        regels.append(
            f"<h2 style=\"font-size:17px;margin:28px 0 10px;padding-bottom:6px;"
            f"border-bottom:2px solid {RAND};\">{escape(persoon)} "
            f"<span style=\"font-weight:400;color:{GRIJS};font-size:13px;\">"
            f"&middot; {len(beoordelingen)} uitvra{'gen' if len(beoordelingen) != 1 else 'ag'}"
            f"</span></h2>"
        )
        for beoordeling in beoordelingen:
            u = beoordeling.uitvraag
            kleur = _badge_kleur(beoordeling.score)
            badge_nieuw = (
                "<span style=\"background:#dbeafe;color:#1e40af;font-size:11px;"
                "padding:2px 6px;border-radius:4px;margin-left:6px;\">NIEUW</span>"
                if u.sleutel in nieuw
                else ""
            )
            regels.append(
                f"<div style=\"border:1px solid {RAND};border-left:4px solid {kleur};"
                f"border-radius:6px;padding:12px 14px;margin:0 0 10px;\">"
                f"<div>"
                f"<span style=\"display:inline-block;background:{kleur};color:#fff;"
                f"font-weight:700;font-size:13px;padding:2px 8px;border-radius:4px;"
                f"margin-right:8px;\">{beoordeling.score}/10</span>"
                f"<a href=\"{escape(u.url, quote=True)}\" "
                f"style=\"color:#1d4ed8;font-weight:600;text-decoration:none;\">"
                f"{escape(u.titel)}</a>{badge_nieuw}"
                f"</div>"
                f"<div style=\"color:{GRIJS};font-size:13px;margin:6px 0 0;\">"
                f"{' &middot; '.join(escape(f) for f in _feiten(beoordeling))}</div>"
                f"<div style=\"color:#374151;font-size:13px;margin:6px 0 0;\">"
                f"<strong>Waarom:</strong> {escape(beoordeling.toelichting)}</div>"
                + (
                    f"<div style=\"color:{GRIJS};font-size:12px;margin:6px 0 0;\">"
                    f"{escape(_fragment(u.omschrijving))}</div>"
                    if u.omschrijving
                    else ""
                )
                + "</div>"
            )

    zonder = [n for n, v in per_persoon.items() if not v]
    if zonder:
        regels.append(
            f"<p style=\"color:{GRIJS};font-size:13px;margin:24px 0 0;\">"
            f"Geen match boven de drempel voor: {escape(', '.join(zonder))}.</p>"
        )

    regels.append(
        f"<h2 style=\"font-size:15px;margin:28px 0 8px;padding-bottom:6px;"
        f"border-bottom:1px solid {RAND};\">Platformstatus</h2>"
        "<table style=\"width:100%;border-collapse:collapse;font-size:13px;\">"
    )
    for status in sorted(platformstatus, key=lambda s: s.platform.lower()):
        teken = "&#10003;" if status.gelukt else "&#9888;"
        kleur = "#15803d" if status.gelukt else "#b45309"
        melding = status.melding or ("" if status.gelukt else "niet opgehaald")
        regels.append(
            f"<tr>"
            f"<td style=\"padding:4px 8px 4px 0;color:{kleur};width:20px;\">{teken}</td>"
            f"<td style=\"padding:4px 8px 4px 0;\">{escape(status.platform)}</td>"
            f"<td style=\"padding:4px 8px 4px 0;text-align:right;white-space:nowrap;\">"
            f"{status.aantal}</td>"
            f"<td style=\"padding:4px 0;color:{GRIJS};\">{escape(melding)}</td>"
            f"</tr>"
        )
    regels.append("</table>")

    regels.append(
        f"<p style=\"color:{GRIJS};font-size:12px;margin:24px 0 0;\">"
        f"Scores komen uit profiles.yaml in de repository opdrachtplatforms. "
        f"Pas dat bestand aan om te sturen wat je hier ziet; de drempel staat in config.yaml.</p>"
    )
    regels.append("</div>")
    return "\n".join(regels)


def maak_tekst(
    per_persoon: dict[str, list[Beoordeling]],
    platformstatus: list[PlatformResultaat],
    nieuw: set[str],
    drempel: int,
    vandaag: date,
    totaal_uitvragen: int,
) -> str:
    week = vandaag.isocalendar().week
    regels = [
        f"OPDRACHTALERT INNOVATIEGROEP - week {week} ({vandaag.strftime('%d-%m-%Y')})",
        f"{totaal_uitvragen} uitvragen bekeken, drempel score {drempel}.",
        "",
    ]
    for persoon, beoordelingen in per_persoon.items():
        if not beoordelingen:
            continue
        regels.append(f"== {persoon} ({len(beoordelingen)}) ==")
        for b in beoordelingen:
            merk = " [NIEUW]" if b.uitvraag.sleutel in nieuw else ""
            regels.append(f"  {b.score}/10{merk} {b.uitvraag.titel}")
            regels.append(f"     {' | '.join(_feiten(b))}")
            regels.append(f"     Waarom: {b.toelichting}")
            regels.append(f"     {b.uitvraag.url}")
        regels.append("")

    zonder = [n for n, v in per_persoon.items() if not v]
    if zonder:
        regels.append(f"Geen match boven de drempel voor: {', '.join(zonder)}.")
        regels.append("")

    regels.append("Platformstatus:")
    for status in sorted(platformstatus, key=lambda s: s.platform.lower()):
        teken = "ok " if status.gelukt else "LET OP"
        melding = f" - {status.melding}" if status.melding else ""
        regels.append(f"  {teken} {status.platform}: {status.aantal} uitvragen{melding}")
    return "\n".join(regels)
