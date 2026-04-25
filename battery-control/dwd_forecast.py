#!/usr/bin/python3
#
# Fetches DWD MOSMIX_L weather forecasts for a configurable station and
# publishes estimates to MQTT so that the price_optimizer module can decide
# whether PV production will cover the battery's charging needs.
#
# Published topics
#   /forecast/pv_energy_today     – estimated PV yield for today (kWh)
#   /forecast/pv_energy_tomorrow  – estimated PV yield for tomorrow (kWh)
#   /forecast/avg_wind_ms         – mean wind speed over the next 24 h (m/s)
#   /forecast/wind_factor         – wind speed normalised to [0, 1] (10 m/s = 1)
#   /forecast/season              – "summer" (Apr–Sep) or "winter" (Oct–Mar)
#
# Config key: "dwd_forecast" in config.json
#   station_id        DWD station identifier, e.g. "P755"
#   panel_area_m2     total PV panel area in m²
#   panel_efficiency  PV panel efficiency (default 0.18)

import io
import json
import time
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

import paho.mqtt.client as mqtt
import requests

DWD_NS = 'https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd'
DWD_BASE = (
    'https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L'
    '/single_stations/{sid}/kml/MOSMIX_L_LATEST_{sid}.kmz'
)


def fetch_dwd_forecast(station_id):
    """Download and parse the MOSMIX_L KMZ file for *station_id*."""
    url = DWD_BASE.format(sid=station_id)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        kml_name = next(n for n in z.namelist() if n.endswith('.kml'))
        return ET.fromstring(z.read(kml_name))


def parse_timestamps(root):
    """Return a list of UTC-aware datetimes for each forecast step."""
    steps_elem = root.find(f'.//{{{DWD_NS}}}ForecastTimeSteps')
    if steps_elem is None:
        return []
    return [
        datetime.fromisoformat(ts.text.replace('Z', '+00:00'))
        for ts in steps_elem.findall(f'{{{DWD_NS}}}TimeStep')
    ]


def parse_parameter(root, name):
    """Return a list of float values for DWD parameter *name*, or None where missing."""
    attr_key = f'{{{DWD_NS}}}elementName'
    for elem in root.iter(f'{{{DWD_NS}}}Forecast'):
        if elem.get(attr_key) == name:
            val_elem = elem.find(f'{{{DWD_NS}}}value')
            if val_elem is not None and val_elem.text:
                result = []
                for token in val_elem.text.split():
                    try:
                        v = float(token)
                        result.append(None if v != v else v)  # guard against NaN
                    except ValueError:
                        result.append(None)
                return result
    return []


def estimate_pv_energy(timestamps, radiation, target_date, panel_area_m2, efficiency):
    """Estimate total PV yield for *target_date* in kWh.

    DWD Rad1h is global horizontal irradiance integrated over the hour in kJ/m².
    Energy [kWh] = Rad1h [kJ/m²] * area [m²] * η / 3600
    """
    total = 0.0
    for ts, rad in zip(timestamps, radiation):
        if ts.date() == target_date and rad is not None and rad > 0:
            total += rad * panel_area_m2 * efficiency / 3600.0
    return total


def estimate_avg_wind_speed(timestamps, wind, hours=24):
    """Average wind speed (m/s) over the next *hours* hours."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours)
    values = [w for ts, w in zip(timestamps, wind)
              if now <= ts <= cutoff and w is not None]
    return sum(values) / len(values) if values else 0.0


def is_summer():
    return datetime.now().month in range(4, 10)


with open('config.json') as f:
    config = json.load(f)

dwd_cfg = config.get('dwd_forecast', {})
station_id = dwd_cfg.get('station_id', 'P755')
panel_area = float(dwd_cfg.get('panel_area_m2', 20.0))
efficiency = float(dwd_cfg.get('panel_efficiency', 0.18))

client = mqtt.Client(client_id='dwd_forecast')
client.connect(
    config['broker']['address'],
    config['broker'].get('port', 1883),
    config['broker'].get('keepalive', 60),
)

last_fetch = 0

while True:
    if time.time() - last_fetch >= 3600:
        try:
            root = fetch_dwd_forecast(station_id)
            timestamps = parse_timestamps(root)
            radiation = parse_parameter(root, 'Rad1h')
            wind = parse_parameter(root, 'FF')

            today = datetime.now(timezone.utc).date()
            tomorrow = today + timedelta(days=1)

            pv_today = estimate_pv_energy(timestamps, radiation, today, panel_area, efficiency)
            pv_tomorrow = estimate_pv_energy(timestamps, radiation, tomorrow, panel_area, efficiency)
            avg_wind = estimate_avg_wind_speed(timestamps, wind)
            wind_factor = min(1.0, avg_wind / 10.0)
            season = 'summer' if is_summer() else 'winter'

            client.publish('/forecast/pv_energy_today', round(pv_today, 2), retain=True)
            client.publish('/forecast/pv_energy_tomorrow', round(pv_tomorrow, 2), retain=True)
            client.publish('/forecast/avg_wind_ms', round(avg_wind, 1), retain=True)
            client.publish('/forecast/wind_factor', round(wind_factor, 3), retain=True)
            client.publish('/forecast/season', season, retain=True)

            print(
                f'DWD forecast updated: PV today={pv_today:.1f} kWh, '
                f'tomorrow={pv_tomorrow:.1f} kWh, '
                f'wind={avg_wind:.1f} m/s ({wind_factor:.2f}), season={season}'
            )
            last_fetch = time.time()
        except Exception as e:
            print(f'DWD forecast fetch failed: {e}')

    client.loop(timeout=0.1)
    time.sleep(60)
