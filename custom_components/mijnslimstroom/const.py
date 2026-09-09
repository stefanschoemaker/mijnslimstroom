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
