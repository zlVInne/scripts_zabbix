#!/usr/bin/env python3

import requests
import time
import json
import sys

ACS = "http://localhost:7557"

if len(sys.argv) != 2:
    print("Uso: ./script.py <DEVICE_ID>")
    sys.exit(1)

DEVICE_ID = sys.argv[1]


def refresh_parameters():
    url = f"{ACS}/devices/{DEVICE_ID}/tasks?timeout=3000&connection_request"
    payload = {
        "name": "getParameterValues",
        "parameterNames": [
            # 🔥 ALERTS
            "Device.FaultMgmt.ExpeditedEvent.*."
        ]
    }

    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass


def get_device():
    r = requests.get(f"{ACS}/devices", timeout=10)
    for dev in r.json():
        if dev["_id"] == DEVICE_ID:
            return dev
    return {}


def safe_get(d, path):
    try:
        for p in path:
            d = d[p]
        return d.get("_value", None)
    except:
        return None


# 🔥 FUNÇÃO LLD (ZABBIX)
def get_alerts_lld(dev):
    discovery = {"data": []}

    try:
        expedited = dev["Device"]["FaultMgmt"]["ExpeditedEvent"]
    except:
        return discovery

    for idx, data in expedited.items():
        try:
            notification = safe_get(data, ["NotificationType"])
            problem = safe_get(data, ["SpecificProblem"])
            event_time = safe_get(data, ["EventTime"])  # 🔥 NOVO

            # ✅ FILTRO: apenas novos alarmes
            if notification != "NewAlarm":
                continue

            if not problem:
                continue

            discovery["data"].append({
                "ALERT_ID": str(idx),
                "Problem": problem,
                "EVENT_TIME": event_time  # 🔥 NOVO
            })

        except:
            continue

    return discovery


def main():
    refresh_parameters()
    time.sleep(10)

    dev = get_device()

    alerts = get_alerts_lld(dev)

    # 🔥 SAÍDA LIMPA PARA ZABBIX LLD
    print(json.dumps(alerts, indent=2))


if __name__ == "__main__":
    main()

