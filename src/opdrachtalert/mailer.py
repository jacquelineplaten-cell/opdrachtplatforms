"""Versturen van de alert via SMTP (standaard Gmail met een app-wachtwoord)."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, formatdate

log = logging.getLogger(__name__)


class MailInstellingen:
    def __init__(self) -> None:
        self.host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.poort = int(os.environ.get("SMTP_PORT", "587"))
        self.gebruiker = os.environ.get("SMTP_USER", "").strip()
        self.wachtwoord = os.environ.get("SMTP_PASSWORD", "").strip()
        self.afzendernaam = os.environ.get("MAIL_FROM_NAME", "Opdrachtalert")
        self.afzender = os.environ.get("MAIL_FROM", self.gebruiker).strip()
        self.ontvangers = [
            adres.strip()
            for adres in os.environ.get("MAIL_TO", "").split(",")
            if adres.strip()
        ]

    @property
    def compleet(self) -> bool:
        return bool(self.gebruiker and self.wachtwoord and self.afzender and self.ontvangers)

    def ontbrekend(self) -> list[str]:
        mist = []
        if not self.gebruiker:
            mist.append("SMTP_USER")
        if not self.wachtwoord:
            mist.append("SMTP_PASSWORD")
        if not self.afzender:
            mist.append("MAIL_FROM")
        if not self.ontvangers:
            mist.append("MAIL_TO")
        return mist


def bouw_bericht(
    instellingen: MailInstellingen, onderwerp: str, tekst: str, html: str
) -> EmailMessage:
    bericht = EmailMessage()
    bericht["Subject"] = onderwerp
    bericht["From"] = formataddr((instellingen.afzendernaam, instellingen.afzender))
    bericht["To"] = ", ".join(instellingen.ontvangers)
    bericht["Date"] = formatdate(localtime=True)
    bericht.set_content(tekst)
    bericht.add_alternative(html, subtype="html")
    return bericht


def verstuur(instellingen: MailInstellingen, bericht: EmailMessage) -> None:
    with smtplib.SMTP(instellingen.host, instellingen.poort, timeout=60) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(instellingen.gebruiker, instellingen.wachtwoord)
        server.send_message(bericht)
    log.info("Mail verstuurd naar %s", ", ".join(instellingen.ontvangers))
