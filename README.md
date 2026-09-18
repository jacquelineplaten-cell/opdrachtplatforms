# Opdrachtalert innovatiegroep

Elke vrijdagochtend om 07:00 één e-mail met de opdrachten die deze week bij het
team passen: per persoon, gescoord van 1 tot 10, en alleen wat 7 of hoger haalt.

De scoring is regelgebaseerd en volledig na te lezen: elk punt komt uit een
trefwoord dat in [`profiles.yaml`](profiles.yaml) staat. Er komt geen AI aan te
pas, dus er zijn geen API-kosten en je kunt altijd terugzien waarom iets in de
mail stond.

## Wat er gescand wordt

| Platform | Hoe we het ophalen | Bijzonderheden |
| --- | --- | --- |
| **Between** en **HeadFirst** | Publieke Striive-API (`striive-cms.codebridge.nl/api/jobs`) | Beide sites tonen dezelfde Striive-lijst, dus we halen die één keer op. Per uitvraag staat erbij onder welk merk je kunt reageren. |
| **Freep** | Publieke API (`api.freep.nl/v1/assignments`) plus de detailpagina | Enkele honderden uitvragen; de omschrijving halen we alleen op voor uitvragen die na een eerste check kansrijk zijn. |
| **Ukomst** | WordPress REST API (`ukomst.nl/wp-json/wp/v2/jobs`) plus de detailpagina | Klein aanbod, sterk IT-gericht. Storingsberichten die Ukomst soms als opdracht publiceert, filteren we eruit. |
| **Need Staffing** | HTML-lijst, 20 per pagina | Zonder inlog. |
| **Circle8** | HTML, zo nodig via een echte browser | Circle8 staat achter de botbescherming van Vercel. Zie [Circle8](#circle8) hieronder. |
| **Flextender** | Inloggen en daarna de aanvragenlijst | Werkt alleen met inloggegevens. Zie [Flextender](#flextender) hieronder. |

Staat dezelfde opdracht op meerdere platforms, dan zie je hem één keer, met
"staat ook op ..." erbij.

## Hoe de score werkt

Per persoon en per uitvraag tellen we op:

| Onderdeel | Max | Waar het vandaan komt |
| --- | --- | --- |
| Expertise | 3,5 | Vakinhoud, methoden en thema's uit `expertise`. Weegt het zwaarst, want dit is het deel van een profiel dat de teamleden van elkaar onderscheidt. |
| Rol | 2,5 | Een functietitel uit `rollen`. Zwaar als die in de titel van de uitvraag staat, licht als die alleen in de omschrijving voorkomt. |
| Sector | 1,8 | Een opdrachtgever of markt uit `sectoren`. |
| Kern | 1,5 | Innovatiesignalen die voor de hele groep gelden (`kern_termen` in `config.yaml`). |
| Boost | 6,0 | Persoonlijke wensen, zoals "laat mij alle onderwijsuitvragen zien". Telt vol als de term op de opdrachtgever slaat, en voor 40% als hij alleen ergens in de omschrijving staat. |
| Straf | −4,0 per term | Een uitvoerende ICT- of specialistenrol in de titel (developer, beheerder, ondersteuner ...), tenzij die term in het eigen profiel staat. |

Rol en sector wegen bewust licht: bijna iedereen in het team is "kwartiermaker"
of "projectleider" en werkt voor gemeenten, dus daarop scoren betekent dat
dezelfde generieke klus bij iedereen in de mail komt. Expertise is wél
onderscheidend en weegt daarom het zwaarst.

Daarbovenop staat de **innovatiepoort**: past de functietitel en de sector wel,
maar gaat de uitvraag nergens over vernieuwen, dan blijft de score op 6 steken
en haalt hij de drempel niet. Dat voorkomt dat iedere "projectleider bij een
gemeente" bovenaan komt. Een persoonlijke boost omzeilt die poort. Uitzetten kan
met `innovatie_poort.actief: false` in `config.yaml`.

De mail vermeldt bij elke uitvraag waarom hij er staat, bijvoorbeeld:
*rol in titel: innovatiemanager; sector: defensie; expertise: adoptie, roadmap*.

## Sturen wat je ziet

Bijna alles wat je wilt bijstellen, zit in twee bestanden:

- **[`profiles.yaml`](profiles.yaml)** – per persoon `rollen`, `sectoren`,
  `expertise`, `uitsluiten` en `boost`. Krijgt iemand te veel ruis? Haal een
  trefwoord weg. Mist iemand iets? Voeg het toe. Iemand even niet beschikbaar?
  Zet `actief: false`.
- **[`config.yaml`](config.yaml)** – de drempel (`drempel: 7`), het maximum
  aantal uitvragen per persoon, de gewichten, de innovatiepoort en welke
  platforms aanstaan. Te weinig in de mail? Zet `drempel` op 6 en kijk wat
  erbij komt.

Twee kolommen in de Excel waren leeg: **Gaber** en **Mesjka**. Die staan op
`actief: false` en krijgen dus nog geen matches. Zodra hun profiel er is, vul je
hun blok in `profiles.yaml` aan en zet je `actief: true`.

Is de Excel bijgewerkt? Dan zet dit script hem om naar leesbare tekst, zodat je
ziet wat er veranderd is:

```bash
pip install openpyxl
python tools/profielen_uit_excel.py pad/naar/Salesprofielen_innovatie_groep.xlsx
```

`profiles.yaml` wordt met de hand bijgewerkt: de trefwoorden daarin zijn gekozen
uit de antwoorden, niet blind overgenomen.

## Instellen in GitHub

Drie stappen: een app-wachtwoord bij Google maken, drie secrets in GitHub zetten,
en één testrun draaien. Reken op een kwartier.

### Stap 1 — Maak een Google app-wachtwoord

Gmail accepteert je gewone wachtwoord niet voor SMTP. Je hebt een app-wachtwoord
nodig: een code van 16 tekens die alleen voor deze alert geldt en die je later
weer kunt intrekken zonder je eigen wachtwoord te wijzigen.

1. Ga naar https://myaccount.google.com/security en zet **Tweestapsverificatie**
   aan als dat nog niet zo is. Zonder tweestapsverificatie bestaat de optie voor
   app-wachtwoorden niet.
2. Ga daarna naar https://myaccount.google.com/apppasswords.
3. Typ bij de naam iets als `Opdrachtalert` en klik op **Maken**.
4. Google toont een code van 16 tekens in vier groepjes, bijvoorbeeld
   `abcd efgh ijkl mnop`. **Kopieer die nu meteen**, je krijgt hem daarna niet
   meer te zien.
5. Haal de spaties eruit: je gebruikt `abcdefghijklmnop`.

### Stap 2 — Zet de secrets in GitHub

Ga naar
https://github.com/jacquelineplaten-cell/opdrachtplatforms/settings/secrets/actions

Zie je die pagina niet, dan zit je op het verkeerde tabblad: het is
**Settings** (tandwiel bovenin de repository, niet je persoonlijke instellingen)
→ in het linkermenu **Secrets and variables** → **Actions**.

Klik op de groene knop **New repository secret** en vul in:

| Name | Secret |
| --- | --- |
| `SMTP_USER` | je Gmail-adres, bijvoorbeeld `jacquelineplaten@gmail.com` |

Klik op **Add secret**. Herhaal dat voor de andere twee:

| Name | Secret |
| --- | --- |
| `SMTP_PASSWORD` | het app-wachtwoord van 16 tekens uit stap 1, zonder spaties |
| `MAIL_TO` | het adres waar de alert naartoe moet. Meerdere adressen scheid je met een komma. |

De namen zijn hoofdlettergevoelig en moeten exact zo geschreven worden. Na het
opslaan kun je een secret niet meer teruglezen, alleen overschrijven; dat is
normaal.

Deze drie zijn genoeg om te starten. Optioneel:

| Name | Waarvoor |
| --- | --- |
| `FLEXTENDER_USERNAME` en `FLEXTENDER_PASSWORD` | Zet Flextender aan. Zonder deze twee wordt dat platform overgeslagen en staat dat in de mail. |
| `FLEXTENDER_LIST_URL` | De URL van je aanvragenlijst, als de alert hem zelf niet vindt. |
| `MAIL_FROM` | Ander afzenderadres dan `SMTP_USER`. |
| `SMTP_HOST` en `SMTP_PORT` | Alleen als je niet via Gmail verstuurt. |

### Stap 3 — Draai een testrun

1. Klik bovenin de repository op het tabblad **Actions**.
2. Klik in het linkermenu op **Wekelijkse opdrachtalert**.
3. Rechts verschijnt de knop **Run workflow**. Klik die aan, vink
   **Alleen tonen wat er verstuurd zou worden, niet mailen** aan en klik op de
   groene **Run workflow**.
4. Na een minuut verschijnt er een regel in de lijst. Klik erop en daarna op
   **alert**, en open de stap **Alert draaien**. Daar zie je precies welke
   uitvragen er gevonden zijn en onderaan de platformstatus. Er is nog geen mail
   verstuurd.
5. Klopt het beeld? Draai dan hetzelfde nog een keer, maar dan **zonder** het
   vinkje. Nu komt de mail binnen.

Krijg je bij die tweede run de melding *"Deze week is al een alert verstuurd"*,
dan is de wekelijkse bescherming aan het werk. Vink dan ook
**Ook versturen als er deze week al een alert uitging** aan.

Daarna draait hij vanzelf elke vrijdag; je hoeft niets meer te doen.

### Waarom je niets hoeft te mergen

`claude/festive-clarke-m0ojlz` is op dit moment de **default branch** van de
repository. Geplande workflows draaien alleen vanaf de default branch, dus de
vrijdagmail werkt zoals het nu staat. Maak je later een `main` en maak je die
de default, verplaats deze bestanden dan mee — anders valt de alert stil.

### Over de planning

De workflow draait elke vrijdag rond 07:00 Nederlandse tijd. GitHub plant op
UTC, dus er staan twee tijden in (05:00 en 06:00 UTC) — de ene klopt in de
zomertijd, de andere in de wintertijd. GitHub kan een geplande run bovendien tot
een uur uitstellen, dus de workflow hanteert een ruim venster (vrijdag tussen
06:00 en 11:00 lokaal) en bewaakt de alert zélf dat er per week maar één mail
uitgaat: staat er in `state/gezien.json` al een verzending in deze ISO-week, dan
stopt hij.

## Lokaal draaien

```bash
pip install -r requirements.txt
export PYTHONPATH=src

# Alles ophalen en scoren, niets versturen:
python -m opdrachtalert.main --droogloop --uitvoer out/alert.html

# Alleen één platform, met logging:
python -m opdrachtalert.main --droogloop --platform freep -v

# Eén keer ophalen, daarna net zo vaak herscoren als je wilt:
python -m opdrachtalert.main --droogloop --bewaar-ruwe out/ruw.json
python -m opdrachtalert.main --droogloop --lees-ruwe out/ruw.json --drempel 6
```

Open `out/alert.html` in je browser om te zien hoe de mail eruitziet.

Krijgt iemand week na week niets? Kijk dan met `--diagnose` mee:

```bash
python -m opdrachtalert.main --lees-ruwe out/ruw.json --diagnose Vis
```

Dat toont de 25 hoogste scores voor die persoon, ook onder de drempel, met per
uitvraag de puntenopbouw. Zie je scores van 5 en 6, dan is het aanbod er wel maar
net niet raak en helpt het om trefwoorden toe te voegen aan zijn of haar
`expertise`. Blijft alles op 1 of 2 steken, dan stond er die week echt niets
bruikbaars tussen.

Tests:

```bash
pip install pytest
python -m pytest
```

## Twee platforms die aandacht vragen

### Circle8

Circle8 draait achter de botbescherming van Vercel. Vanaf een datacenter-IP
(zoals de GitHub-runner) kan dat een 403 opleveren. De scraper probeert daarom
eerst een gewoon verzoek en daarna een echte browser (Chromium via Playwright),
en leest vervolgens de JSON-LD-vacaturegegevens of anders de links op de pagina.

De browserstap is de traagste van de hele run; in `config.yaml` staat onder
`platforms.circle8` een harde grens (`browser_laad_timeout_seconden`,
`browser_selector_timeout_seconden`) en kun je hem met `gebruik_browser: false`
helemaal overslaan.

Lukt het niet, dan **staat dat met zoveel woorden in de platformstatus onderaan
de mail** en gaat de rest gewoon door. Vanuit de ontwikkelomgeving waarin dit
gebouwd is, bleef Circle8 geblokkeerd; of het vanaf GitHub wél lukt, blijkt bij
de eerste echte run. Zo niet, dan is het alternatief om Circle8's eigen
e-mailalert aan te zetten en die naar dit postvak te laten lopen.

### Flextender

Flextender vereist inlog en elke omgeving heeft een eigen inrichting. De scraper
logt in op https://app.flextender.nl/ en zoekt daarna zelf de pagina met
aanvragen. Vindt hij die niet, of wordt de lijst daar met JavaScript geladen,
dan meldt hij dat in de mail. Zet in dat geval `FLEXTENDER_LIST_URL` op de URL
die je zelf in je browser ziet als je bent ingelogd en naar je aanvragen kijkt.

## Wat de alert onthoudt

`state/gezien.json` houdt twee dingen bij: welke uitvragen al eens in een mail
stonden, en wanneer de laatste mail uitging (dat laatste voorkomt een tweede
mail in dezelfde week).
Nieuwe krijgen het label **NIEUW**; eerder gemelde uitvragen blijven wel staan
zolang ze open zijn, zodat je ze niet kwijtraakt. De workflow commit dat bestand
na iedere verzending terug naar de repository. Bij een droogloop verandert er
niets aan dat geheugen.
