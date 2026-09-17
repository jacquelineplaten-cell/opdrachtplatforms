from opdrachtalert.matching import bevat, normaliseer


def matcht(tekst: str, term: str) -> bool:
    return bevat(normaliseer(tekst), term)


def test_samenstelling_telt_mee():
    assert matcht("Innovatieproces versnellen", "innovatie")
    assert matcht("Innovaties in de keten", "innovatie")
    assert matcht("Onderwijsinstellingen", "onderwijs")
    assert matcht("Projectleider woningbouwopgave", "woningbouw")


def test_korte_termen_zijn_hele_woorden():
    # "AI" mag niet matchen op "detail", "java" niet op "javascript".
    assert not matcht("Detail van de opdracht", "AI")
    assert matcht("Inzet van AI in de keten", "AI")
    assert not matcht("Javascript developer", "java")
    assert matcht("Java developer", "java")
    assert matcht("mbo-instelling", "mbo")
    assert not matcht("Ambochtelijk werk", "mbo")


def test_meerwoordstermen_en_scheidingstekens():
    assert matcht("Adviseur Innovatie bij de gemeente", "adviseur innovatie")
    assert matcht("adviseur  innovatie", "adviseur innovatie")
    assert matcht("co-creatie sessies", "co-creatie")
    assert matcht("Senior Java/Angular", "java")
    assert matcht("werkzaam in het .NET team", ".net")


def test_accenten_en_hoofdletters():
    assert matcht("Strategische heroriëntatie", "strategische herorientatie")
    assert matcht("COÖRDINATOR innovatie", "coördinator")


def test_lege_term_matcht_nooit():
    assert not matcht("wat dan ook", "")
    assert not matcht("wat dan ook", "   ")
