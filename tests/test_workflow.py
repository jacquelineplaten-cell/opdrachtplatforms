"""Bewaking van de workflow zelf.

Op 9 oktober 2026 ging er geen alert uit. Niet omdat de code faalde, maar omdat
de workflow een controle op de lokale tijd had: GitHub stelde de geplande runs
ruim zes uur uit, ze vielen buiten het venster van 06:00-11:00 en beide stopten
zichzelf. De run kreeg een groen vinkje, dus er was geen enkel signaal.

Deze tests houden die constructie buiten de deur.
"""

import re
from pathlib import Path

import yaml

from conftest import WORTEL

WORKFLOW = WORTEL / ".github" / "workflows" / "opdrachtalert.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    """YAML 1.1 leest de sleutel 'on' als de booleaanse waarde True."""
    return workflow.get("on") or workflow[True]


def test_geen_controle_op_de_lokale_tijd():
    """Een uitgestelde run moet alsnog mailen, niet zichzelf weggooien."""
    tekst = WORKFLOW.read_text(encoding="utf-8")
    stappen = _workflow()["jobs"]["alert"]["steps"]

    # Geen enkele stap mag de run afbreken op basis van het uur of de weekdag.
    for stap in stappen:
        commando = stap.get("run", "")
        assert not re.search(r"date \+%H", commando), (
            f"stap {stap.get('name')!r} beslist op het lokale uur; "
            "een door GitHub uitgestelde run verliest dan de hele week"
        )
        assert not re.search(r"date \+%u", commando), (
            f"stap {stap.get('name')!r} beslist op de weekdag"
        )
    assert "doorgaan=nee" not in tekst


def test_cron_staat_op_vrijdag_met_een_reserve():
    schema = _triggers(_workflow())["schedule"]
    assert len(schema) >= 2, "een tweede cron vangt een overgeslagen eerste op"
    for regel in schema:
        velden = regel["cron"].split()
        assert velden[4] == "5", f"{regel['cron']}: moet op vrijdag vallen"


def test_elke_stap_draait_onvoorwaardelijk_of_altijd():
    """Alleen 'always()' mag nog als voorwaarde: verder geen stille overslag."""
    for stap in _workflow()["jobs"]["alert"]["steps"]:
        voorwaarde = stap.get("if")
        assert voorwaarde in (None, "always()"), (
            f"stap {stap.get('name')!r} heeft voorwaarde {voorwaarde!r}"
        )
