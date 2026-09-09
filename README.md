# Mijn SlimStroom

Integraties en apps voor klanten van [Mijn SlimStroom](https://www.mijnslimstroom.nl):
thuisbatterijen die automatisch laden en ontladen op de dynamische
stroomprijzen.

## Home Assistant-integratie (HACS)

Haal je live energiestromen, dagtotalen, saldo, de actuele stroomprijs
en het batterijplan als sensoren in Home Assistant. De integratie
gebruikt dezelfde inloggegevens als de Mijn SlimStroom-app.

### Installatie

1. HACS > Integrations > menu rechtsboven > **Custom repositories**.
2. Voeg `https://github.com/stefanschoemaker/mijnslimstroom` toe als
   type **Integration**.
3. Installeer "Mijn SlimStroom" en herstart Home Assistant.
4. Instellingen > Apparaten & diensten > **Integratie toevoegen** >
   Mijn SlimStroom > log in met je app-gegevens.

### Sensoren

| Sensor | Eenheid | Bijzonderheden |
|---|---|---|
| Zonvermogen, Huisverbruik | W | elke minuut |
| Batterijvermogen | W | + = laden, - = ontladen |
| Netvermogen | W | + = import, - = export |
| Accu | % | |
| Opgewekt / Verbruikt / Geimporteerd / Geexporteerd / Geladen / Ontladen vandaag | kWh | dagteller, bruikbaar in het Energie-dashboard |
| Zelfvoorzienend vandaag | % | per uur gemeten |
| Saldo vandaag | EUR | verdiend minus uitgegeven |
| Stroomprijs | EUR/kWh | actueel kwartier (kaal EPEX) |
| Batterijplan | laden / ontladen / rust | automatiseer op wat de batterij NU doet |

Voorbeeld-automatisering: de vaatwasser starten zodra het plan
"laden" zegt (goedkope stroom) of het huis waarschuwen bij "ontladen"
(dure stroom).

### Validatie-CI (nog toe te voegen)

De standaard hassfest + HACS-validatieworkflow kon niet mee in deze
push (het gebruikte OAuth-token mist de `workflow`-scope). Eenmalig
`gh auth refresh -s workflow` draaien en dit bestand als
`.github/workflows/validate.yaml` toevoegen:

```yaml
name: Validate
on:
  push:
  pull_request:
  schedule:
    - cron: "0 4 * * 1"
jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master
  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration
```

## Android-app

De Android-versie van de Mijn SlimStroom-app staat onder
[Releases](https://github.com/stefanschoemaker/mijnslimstroom/releases)
als APK, met automatische updates in de app zelf.
