"""Inlezen van profiles.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Profiel:
    naam: str
    actief: bool = True
    rollen: list[str] = field(default_factory=list)
    sectoren: list[str] = field(default_factory=list)
    expertise: list[str] = field(default_factory=list)
    uitsluiten: list[str] = field(default_factory=list)
    boost: dict[str, float] = field(default_factory=dict)

    @property
    def heeft_inhoud(self) -> bool:
        return bool(self.rollen or self.sectoren or self.expertise)


def laad_profielen(pad: Path) -> list[Profiel]:
    data = yaml.safe_load(pad.read_text(encoding="utf-8")) or {}
    profielen = []
    for item in data.get("personen", []):
        profielen.append(
            Profiel(
                naam=item["naam"],
                actief=bool(item.get("actief", True)),
                rollen=list(item.get("rollen") or []),
                sectoren=list(item.get("sectoren") or []),
                expertise=list(item.get("expertise") or []),
                uitsluiten=list(item.get("uitsluiten") or []),
                boost={k: float(v) for k, v in (item.get("boost") or {}).items()},
            )
        )
    return profielen


def actieve_profielen(profielen: list[Profiel]) -> list[Profiel]:
    return [p for p in profielen if p.actief and p.heeft_inhoud]
