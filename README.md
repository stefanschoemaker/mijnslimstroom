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

Voorbeeld-automatisering: de vaatwasser starten zodra het plan
"laden" zegt (goedkope stroom) of het huis waarschuwen bij "ontladen"
(dure stroom).

## Android-app

De Android-versie van de Mijn SlimStroom-app staat onder
[Releases](https://github.com/stefanschoemaker/mijnslimstroom/releases)
als APK, met automatische updates in de app zelf.
