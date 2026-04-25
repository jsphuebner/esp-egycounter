#!/usr/bin/python3
#
# Calculates optimal charge and discharge price thresholds and publishes them
# via MQTT so that netzero.py can act on them.
#
# Design principles
#   - PV energy is always the cheapest source; grid charging is only enabled
#     when PV production tomorrow cannot cover the remaining storage deficit.
#   - Two storage configurations are supported automatically:
#       * EV (55 kWh) when pyPlc/fsm_state == "CurrentDemand"
#       * Stationary battery (6 kWh) at all other times
#   - Day-ahead spot market prices (EUR/MWh, from /spotmarket/pricelist) are
#     the primary price signal.
#   - DWD weather forecasts (/forecast/*) fine-tune the decision:
#       * High PV forecast → suppress grid charging (summer mode)
#       * High wind factor → apply a discount to the charge threshold so that
#         grid charging only happens during genuinely cheap wind-driven hours
#         (relevant in winter).
#
# Subscribed topics
#   /spotmarket/pricelist         – JSON price list published by spotmarket.py
#   /forecast/pv_energy_tomorrow  – kWh, from dwd_forecast.py
#   /forecast/wind_factor         – 0–1, from dwd_forecast.py
#   /forecast/season              – "summer" | "winter", from dwd_forecast.py
#   pyPlc/fsm_state               – EV connection state
#   pyPlc/soc                     – EV state of charge (%)
#   pyPlc/soclimit                – EV target SoC (%)
#   pyPlc/target_current          – EV charger target current (A)
#   pyPlc/charger_voltage         – EV charger voltage (V)
#   /bms/info/chargepower         – stationary battery available charge power (W)
#
# Published topics (retain=True)
#   /grid/chargethresh            – charge stationary battery below this price
#   /grid/evchargethresh          – charge EV below this price
#   /grid/dischargethresh         – discharge storage above this price
#
# Config key: "price_optimizer" in config.json
#   ev_capacity_kwh           total EV battery capacity (default 55)
#   stat_capacity_kwh         stationary battery capacity (default 6)
#   stat_max_charge_power_w   max charge power of stationary battery (default 1800)
#   wind_discount_eur_mwh     price threshold reduction per unit of wind_factor
#                             (default 20 EUR/MWh)

import json
import re
import time

import paho.mqtt.client as mqtt

RECALC_INTERVAL = 900   # seconds – recalculate at least every 15 minutes


def ev_is_connected():
    return mqttVal('pyPlc/fsm_state') == 'CurrentDemand'


def ev_energy_needed_kwh():
    """kWh still needed to reach the EV's SoC limit."""
    soc = mqttVal('pyPlc/soc', 0)
    soc_limit = mqttVal('pyPlc/soclimit', 85)
    return max(0.0, (soc_limit - soc) / 100.0 * ev_capacity_kwh)


def stat_energy_needed_kwh():
    """Rough kWh estimate for the stationary battery based on available charge power."""
    charge_power_w = mqttVal('/bms/info/chargepower', 0)
    fraction_needed = min(1.0, charge_power_w / stat_max_charge_w)
    return fraction_needed * stat_capacity_kwh * 0.8


def energy_needed_kwh():
    return ev_energy_needed_kwh() if ev_is_connected() else stat_energy_needed_kwh()


def get_future_prices():
    """Return a list of (marketprice_eur_mwh, start_timestamp_ms) for future slots."""
    data = mqttVal('/spotmarket/pricelist', {})
    items = data.get('data', []) if isinstance(data, dict) else []
    now_ms = time.time() * 1000
    return [
        (float(item['marketprice']), int(item['start_timestamp']))
        for item in items
        if item.get('start_timestamp', 0) >= now_ms
    ]


def calculate_thresholds():
    future = get_future_prices()
    if not future:
        print('No price data available, skipping threshold update')
        return

    prices = [p for p, _ in future]
    sorted_prices = sorted(prices)
    avg_price = sum(prices) / len(prices)
    median_price = sorted_prices[len(sorted_prices) // 2]

    pv_tomorrow = mqttVal('/forecast/pv_energy_tomorrow', 5.0)
    wind_factor = mqttVal('/forecast/wind_factor', 0.0)
    season = mqttVal('/forecast/season', 'summer')

    needed = energy_needed_kwh()

    # Discharge threshold: only discharge when the price is above average,
    # ensuring we recoup the cost of the energy stored.
    discharge_thresh = avg_price

    # --- Charge threshold ---
    # In summer, if tomorrow's PV forecast can cover the remaining deficit, we
    # should never occupy storage with grid energy.
    pv_covers_deficit = pv_tomorrow >= needed * 0.8
    if season == 'summer' and pv_covers_deficit:
        charge_thresh = -9999.0
        ev_charge_thresh = -9999.0
        print(
            f'PV tomorrow ({pv_tomorrow:.1f} kWh) covers deficit '
            f'({needed:.1f} kWh): grid charging suppressed'
        )
    else:
        # Determine how many cheap hours are needed to cover the deficit.
        if ev_is_connected():
            target_a = mqttVal('pyPlc/target_current', 16)
            voltage_v = mqttVal('pyPlc/charger_voltage', 400)
            charging_kw = max(1.0, min(
                target_a * voltage_v / 1000.0,
                config['netzero']['evpower'] / 1000.0,
            ))
        else:
            charging_kw = stat_max_charge_w / 1000.0

        hours_needed = max(1, round(needed / charging_kw))
        hours_needed = min(hours_needed, len(sorted_prices))

        # In winter, high wind production drives spot prices down.  Apply a
        # discount so that we capture those wind-driven cheap hours even when
        # the absolute price level is moderate.
        wind_discount = wind_factor * wind_discount_eur_mwh

        charge_thresh = sorted_prices[hours_needed - 1] - wind_discount
        ev_charge_thresh = charge_thresh

        print(
            f'Charging plan: needed={needed:.1f} kWh, '
            f'{hours_needed} h at {charging_kw:.1f} kW, '
            f'charge_thresh={charge_thresh:.1f} EUR/MWh, '
            f'discharge_thresh={discharge_thresh:.1f} EUR/MWh, '
            f'wind_discount={wind_discount:.1f}'
        )

    client.publish('/grid/chargethresh', round(charge_thresh, 1), retain=True)
    client.publish('/grid/evchargethresh', round(ev_charge_thresh, 1), retain=True)
    client.publish('/grid/dischargethresh', round(discharge_thresh, 1), retain=True)


def on_message(client, userdata, msg):
    global mqttData, last_recalc

    payload = msg.payload.decode('utf-8')

    if msg.topic == '/spotmarket/pricelist':
        try:
            mqttData[msg.topic] = json.loads(payload)
        except json.JSONDecodeError:
            return
    elif re.match(r'^-?\d+[\.,]*\d*$', payload):
        mqttData[msg.topic] = float(payload.replace(',', '.'))
    else:
        mqttData[msg.topic] = payload

    # Recalculate immediately on price or forecast updates and on EV state changes.
    if msg.topic in (
        '/spotmarket/pricelist',
        '/forecast/pv_energy_tomorrow',
        '/forecast/wind_factor',
        '/forecast/season',
        'pyPlc/fsm_state',
        'pyPlc/soc',
    ):
        calculate_thresholds()
        last_recalc = time.time()


def mqttVal(key, default=0):
    return mqttData.get(key, default)


with open('config.json') as f:
    config = json.load(f)

opt_cfg = config.get('price_optimizer', {})
ev_capacity_kwh = float(opt_cfg.get('ev_capacity_kwh', 55))
stat_capacity_kwh = float(opt_cfg.get('stat_capacity_kwh', 6))
stat_max_charge_w = float(opt_cfg.get('stat_max_charge_power_w', 1800))
wind_discount_eur_mwh = float(opt_cfg.get('wind_discount_eur_mwh', 20))

client = mqtt.Client(client_id='price_optimizer')
client.on_message = on_message
client.connect(
    config['broker']['address'],
    config['broker'].get('port', 1883),
    config['broker'].get('keepalive', 60),
)

for topic in (
    '/spotmarket/pricelist',
    '/forecast/pv_energy_tomorrow',
    '/forecast/wind_factor',
    '/forecast/season',
    'pyPlc/fsm_state',
    'pyPlc/soc',
    'pyPlc/soclimit',
    'pyPlc/target_current',
    'pyPlc/charger_voltage',
    '/bms/info/chargepower',
):
    client.subscribe(topic)

mqttData = {}
last_recalc = 0

while True:
    client.loop(timeout=0.1)
    if time.time() - last_recalc > RECALC_INTERVAL:
        calculate_thresholds()
        last_recalc = time.time()
    time.sleep(10)
