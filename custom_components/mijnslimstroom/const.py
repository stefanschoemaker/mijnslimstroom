"""Constanten voor de Mijn SlimStroom-integratie."""

from __future__ import annotations

DOMAIN = "mijnslimstroom"
BASE_URL = "https://app.mijnslimstroom.nl"

# Live-vermogens elke minuut; de tragere blokken (dagtotalen, saldo,
# prijs, batterijplan) om de 5 minuten - dezelfde cadans waarmee de
# bron zelf beweegt (kwartierplan, uurprijzen, dagtellers).
UPDATE_INTERVAL_SECONDS = 60
SLOW_EVERY_N_TICKS = 5

CONF_SITE_ID = "site_id"
CONF_DISPLAY_NAME = "display_name"

# Opties (Instellingen > Apparaten en diensten > Mijn SlimStroom >
# Configureren): per slim apparaat de entiteiten die zeggen dat het
# draait en wat het verbruikt. Zie tracker.py.
OPT_LOADS = "loads"
OPT_RUNNING_ENTITY = "running_entity"
OPT_ENERGY_ENTITY = "energy_entity"
OPT_THRESHOLD_W = "threshold_w"
DEFAULT_THRESHOLD_W = 50
# Een draaibeurt korter dan dit is een schakelglitch, geen draaibeurt.
MIN_RUN_SECONDS = 120
SERVICE_REPORT_RUN = "meld_apparaat"

# Meters terugmelden (opties > Meters koppelen): per meter een sensor
# met de totale energie in kWh. Zie meters.py.
OPT_METERS = "meters"
METERS = ("heatpump", "ev_charger", "solar")
METER_INTERVAL_SECONDS = 300
# Een stilstaande teller toch af en toe melden, zodat de reeks doorloopt.
METER_REPEAT_SECONDS = 1800

# Prijzen vanaf vandaag 00:00: de bekende dagprijzen en daarna de
# prijsverwachting, zover die reikt (de server kapt lege dagen af).
PRICE_DAYS = 4

VERSION = "1.5.0"
CLIENT_HEADERS = {"X-Client": "home-assistant", "X-Client-Version": VERSION}
