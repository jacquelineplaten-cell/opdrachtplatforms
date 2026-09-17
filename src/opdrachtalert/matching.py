"""Nederlandse termmatching: hele woorden, met ruimte voor samenstellingen."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

# Termen vanaf deze lengte mogen ook het begin van een samenstelling zijn:
# "innovatie" matcht dan ook "innovatieproces" en "innovatievermogen".
# Kortere termen ("AI", "mbo", "java") moeten een heel woord zijn, anders
# matcht "AI" op "detail" en "java" op "javascript".
MIN_LENGTE_SAMENSTELLING = 6


def normaliseer(tekst: str) -> str:
    """Kleine letters, accenten weg, koppeltekens en leestekens naar spaties."""
    if not tekst:
        return ""
    ontleed = unicodedata.normalize("NFKD", tekst)
    zonder_accent = "".join(c for c in ontleed if not unicodedata.combining(c))
    kleingemaakt = zonder_accent.lower()
    # Punten binnen termen als ".net" willen we houden; de rest wordt een spatie.
    opgeschoond = re.sub(r"[^a-z0-9.+&/ ]+", " ", kleingemaakt)
    return " ".join(opgeschoond.split())


@lru_cache(maxsize=4096)
def _patroon(term: str) -> re.Pattern[str]:
    genormaliseerd = normaliseer(term)
    woorden = genormaliseerd.split()
    if not woorden:
        # Kan nooit matchen; voorkomt een patroon dat op alles aanslaat.
        return re.compile(r"(?!x)x")

    delen = [re.escape(w) for w in woorden]
    kern = r"[\s/-]+".join(delen)

    laatste = woorden[-1]
    if len(genormaliseerd.replace(" ", "")) >= MIN_LENGTE_SAMENSTELLING and laatste.isalpha():
        # Sta een samenstelling of meervoud toe na het laatste woord.
        staart = r"[a-z]*"
    else:
        staart = r""

    return re.compile(rf"(?<![a-z0-9]){kern}{staart}(?![a-z0-9])")


def bevat(tekst_genormaliseerd: str, term: str) -> bool:
    return bool(_patroon(term).search(tekst_genormaliseerd))


def gevonden_termen(tekst_genormaliseerd: str, termen: list[str]) -> list[str]:
    """De termen uit de lijst die in de tekst voorkomen, in de oorspronkelijke spelling."""
    return [t for t in termen if bevat(tekst_genormaliseerd, t)]
