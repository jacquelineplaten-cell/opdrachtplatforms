"""Register van beschikbare platformscrapers."""

from . import circle8, flextender, freep, needstaffing, striive, ukomst

SCRAPERS = {
    "striive": striive.haal_op,       # Between + HeadFirst (+ StarApple)
    "freep": freep.haal_op,
    "ukomst": ukomst.haal_op,
    "needstaffing": needstaffing.haal_op,
    "circle8": circle8.haal_op,
    "flextender": flextender.haal_op,
}

__all__ = ["SCRAPERS"]
