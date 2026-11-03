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

**Energie-dashboard**: netverbruik = *Geimporteerd vandaag* met
prijs-entiteit *Stroomprijs*; teruglevering = *Geexporteerd vandaag*
met prijs-entiteit *Terugleverprijs*; zonnepanelen = *Opgewekt
vandaag*; thuisbatterij = *Geladen* / *Ontladen vandaag*. Zo rekent
Home Assistant de kosten met dezelfde tarieven als de app.
| Zelfvoorzienend vandaag | % | per uur gemeten |
| Saldo vandaag | EUR | verdiend minus uitgegeven |
| Stroomprijs | EUR/kWh | actueel kwartier, inclusief leveringsmarge, energiebelasting en btw (of het vaste tarief); kaal EPEX als er geen contract is ingesteld |
| Terugleverprijs | EUR/kWh | wat teruglevering nu oplevert (saldering/vast/dynamisch) |
| Batterijplan | laden / ontladen / rust | automatiseer op wat de batterij NU doet |

#### Slimme momenten (vanaf 1.1.0, alleen als u ze aanzet in de app)

Zet in de app **Account > Slimme apparaten** de slimme momenten aan en
voeg uw apparaten toe (boiler, vaatwasser, pomp, ...). De integratie
maakt dan extra entiteiten aan:

| Entiteit | Wat het is |
|---|---|
| Stroomprijs nu | goedkoop / normaal / duur, ten opzichte van de komende 24 uur |
| Goedkoopste 2 uur start | begin van de goedkoopste twee uur in de komende 24 uur |
| Negatieve prijs nu / Volgende negatieve prijs | de uren waarin stroom geld oplevert |
| Verwarmingsadvies | bijstoken / normaal / temperen (als u het advies aanzet) |
| *Apparaat* nu gunstig | aan zolang het aanbevolen venster loopt: start hierop uw automatisering |
| *Apparaat* beste start | starttijd van het aanbevolen venster (attributen: einde, reden, verwachting) |
| *Apparaat* besparing | wat het venster scheelt ten opzichte van nu starten, in euro |

Voorbeeld: automatisering "als *Boiler nu gunstig* aan gaat, zet de
boiler-boost aan". De aanbevelingen volgen de planning van uw batterij
en zijn na de bekende dagprijzen een verwachting (attribuut
`verwachting`).

Voorbeeld-automatisering: de vaatwasser starten zodra het plan
"laden" zegt (goedkope stroom) of het huis waarschuwen bij "ontladen"
(dure stroom).

#### Draaibeurten terugmelden (vanaf 1.2.0)

De integratie kan ook terugmelden wanneer een slim apparaat echt
draaide en wat het verbruikte. Ga naar **Instellingen > Apparaten en
diensten > Mijn SlimStroom > Configureren**, kies het apparaat en
koppel:

- een **loopt-entiteit** (schakelaar, binaire sensor of statussensor
  die aan/run staat zolang het apparaat draait), en/of
- een **energie-entiteit**: een kWh-teller of een vermogen in W
  (slimme stekker). Zonder loopt-entiteit geldt: vermogen boven de
  drempel (standaard 50 W) = draait.

Elke draaibeurt (langer dan twee minuten) wordt aan de app gemeld: bij
de start en bij het einde met de gemeten kWh. De app laat per apparaat
zien of het op het aanbevolen moment draaide en wat dat bespaarde; na
drie gemeten draaibeurten vervangen het gemeten verbruik en de gemeten
draaitijd de ingestelde waarden (uit te zetten per apparaat in de app).

| Entiteit | Wat het is |
|---|---|
| *Apparaat* laatste besparing | wat de laatste draaibeurt bespaarde ten opzichte van het duurste moment van die dag |
| *Apparaat* op aanbevolen moment | percentage van de draaibeurten (30 dagen) dat in een aanbevolen venster startte; attributen: aantal keren, kWh, loopt sinds |

Eigen automatisering zonder koppeling: de actie
`mijnslimstroom.meld_apparaat` met `load_id`, `started_at` en
optioneel `ended_at` en `kwh`.

## Android-app

De Android-versie van de Mijn SlimStroom-app staat onder
[Releases](https://github.com/stefanschoemaker/mijnslimstroom/releases)
als APK, met automatische updates in de app zelf.
