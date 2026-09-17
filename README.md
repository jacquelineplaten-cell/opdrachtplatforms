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

Zet deze secrets onder **Settings → Secrets and variables → Actions**:

| Secret | Nodig? | Waarde |
| --- | --- | --- |
| `SMTP_USER` | ja | Het Gmail-adres waarmee verstuurd wordt. |
| `SMTP_PASSWORD` | ja | Een Google **app-wachtwoord**, niet je gewone wachtwoord. Aanmaken op https://myaccount.google.com/apppasswords (tweestapsverificatie moet aanstaan). |
| `MAIL_TO` | ja | De ontvanger(s), komma's ertussen voor meerdere. |
| `MAIL_FROM` | nee | Afzenderadres; standaard hetzelfde als `SMTP_USER`. |
| `SMTP_HOST` / `SMTP_PORT` | nee | Alleen als je niet via Gmail wilt versturen. Standaard `smtp.gmail.com` en `587`. |
| `FLEXTENDER_USERNAME` | nee | Je Flextender-inlog. Zonder dit wordt Flextender overgeslagen. |
| `FLEXTENDER_PASSWORD` | nee | Bijbehorend wachtwoord. |
| `FLEXTENDER_LIST_URL` | nee | De URL van de aanvragenlijst die je na inloggen ziet. Zie hieronder. |

De workflow [`.github/workflows/opdrachtalert.yml`](.github/workflows/opdrachtalert.yml)
draait elke vrijdag. GitHub plant op UTC, dus er staan twee tijden in (05:00 en
06:00 UTC); de eerste stap laat alleen de run door die in Amsterdam echt 07:00
is. Zo klopt de tijd ook na de overgang naar wintertijd.

Je kunt hem ook met de hand starten via **Actions → Wekelijkse opdrachtalert →
Run workflow**, eventueel als droogloop of met een andere drempel.

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

`state/gezien.json` houdt bij welke uitvragen al eens in een mail stonden.
Nieuwe krijgen het label **NIEUW**; eerder gemelde uitvragen blijven wel staan
zolang ze open zijn, zodat je ze niet kwijtraakt. De workflow commit dat bestand
na iedere verzending terug naar de repository. Bij een droogloop verandert er
niets aan dat geheugen.
