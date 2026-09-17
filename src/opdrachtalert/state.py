"""Onthouden welke uitvragen al eens in een alert stonden."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


class Geheugen:
    def __init__(self, pad: Path) -> None:
        self.pad = pad
        self._gezien: dict[str, str] = {}
        self._laatste_verzending: date | None = None
        if pad.exists():
            try:
                data = json.loads(pad.read_text(encoding="utf-8"))
                self._gezien = {str(k): str(v) for k, v in (data.get("gezien") or {}).items()}
                stempel = data.get("laatste_verzending")
                self._laatste_verzending = date.fromisoformat(stempel) if stempel else None
            except (json.JSONDecodeError, OSError, ValueError, TypeError):
                self._gezien = {}
                self._laatste_verzending = None

    def is_nieuw(self, sleutel: str) -> bool:
        return sleutel not in self._gezien

    @property
    def laatste_verzending(self) -> date | None:
        return self._laatste_verzending

    def al_verstuurd_deze_week(self, vandaag: date) -> bool:
        """Beschermt tegen dubbel verzenden als een run later opnieuw start.

        GitHub kan een geplande run tot een uur uitstellen, en een handmatige
        run kan er nog eens overheen komen. We kijken daarom naar de ISO-week:
        is er in deze week al een mail uitgegaan, dan slaan we hem over.
        """
        vorige = self._laatste_verzending
        if not vorige:
            return False
        return vorige.isocalendar()[:2] == vandaag.isocalendar()[:2]

    def noteer_verzending(self, vandaag: date) -> None:
        self._laatste_verzending = vandaag

    def noteer(self, sleutels: list[str], vandaag: date | None = None) -> None:
        stempel = (vandaag or date.today()).isoformat()
        for sleutel in sleutels:
            self._gezien.setdefault(sleutel, stempel)

    def opschonen(self, bewaar_dagen: int = 180, vandaag: date | None = None) -> None:
        grens = (vandaag or date.today()).toordinal() - bewaar_dagen
        self._gezien = {
            sleutel: stempel
            for sleutel, stempel in self._gezien.items()
            if _ordinaal(stempel) >= grens
        }

    def opslaan(self) -> None:
        self.pad.parent.mkdir(parents=True, exist_ok=True)
        inhoud = {
            "laatste_verzending": (
                self._laatste_verzending.isoformat() if self._laatste_verzending else None
            ),
            "gezien": self._gezien,
        }
        self.pad.write_text(json.dumps(inhoud, indent=1, sort_keys=True), encoding="utf-8")


def _ordinaal(stempel: str) -> int:
    try:
        return date.fromisoformat(stempel).toordinal()
    except ValueError:
        return 0
