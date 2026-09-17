"""Onthouden welke uitvragen al eens in een alert stonden."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


class Geheugen:
    def __init__(self, pad: Path) -> None:
        self.pad = pad
        self._gezien: dict[str, str] = {}
        if pad.exists():
            try:
                data = json.loads(pad.read_text(encoding="utf-8"))
                self._gezien = {str(k): str(v) for k, v in (data.get("gezien") or {}).items()}
            except (json.JSONDecodeError, OSError):
                self._gezien = {}

    def is_nieuw(self, sleutel: str) -> bool:
        return sleutel not in self._gezien

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
        self.pad.write_text(
            json.dumps({"gezien": self._gezien}, indent=1, sort_keys=True), encoding="utf-8"
        )


def _ordinaal(stempel: str) -> int:
    try:
        return date.fromisoformat(stempel).toordinal()
    except ValueError:
        return 0
