#!/usr/bin/env python3

import requests
import time
import json
import sys
from datetime import datetime, timezone

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

            # DeviceInfo
            "Device.DeviceInfo.ModelName",
            "Device.DeviceInfo.SerialNumber",
            "Device.DeviceInfo.SoftwareVersion",
            "Device.DeviceInfo.HardwareVersion",
            "Device.DeviceInfo.Manufacturer",
            "Device.DeviceInfo.UpTime",

            # ACS
            "Device.ManagementServer.URL",
            "Device.ManagementServer.NATDetected",
            "Device.ManagementServer.PeriodicInformInterval",

            # LTE / possíveis S1 paths
            "Device.Services.FAPService.1.FAPControl.LTE.Gateway.X_681D64_S1Status",
            "Device.Services.FAPService.1.FAPControl.LTE.X_BBU_S1Status",
            "Device.Services.FAPService.1.FAPControl.LTE.S1Status",

            # UE
            "Device.Services.FAPService.1.FAPControl.LTE.UeNumberOfEntries",

            # Alarm
            "Device.Services.FAPService.1.FAPControl.LTE.Alarm.CurrentAlarmNumberOfEntries",
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


# 🔥 fallback inteligente
def get_first_valid(dev, paths):
    for p in paths:
        val = safe_get(dev, p)
        if val is not None:
            return val
    return None


def calculate_uptime_from_lastboot(last_boot):
    if not last_boot:
        return None

    try:
        bt = datetime.fromisoformat(last_boot.replace("Z", "+00:00"))
    except:
        return None

    now = datetime.now(timezone.utc)
    return int((now - bt).total_seconds())


def main():
    refresh_parameters()
    time.sleep(8)

    dev = get_device()

    # DeviceInfo
    device_info = {
        "ModelName": safe_get(dev, ["Device", "DeviceInfo", "ModelName"]),
        "SerialNumber": safe_get(dev, ["Device", "DeviceInfo", "SerialNumber"]),
        "SoftwareVersion": safe_get(dev, ["Device", "DeviceInfo", "SoftwareVersion"]),
        "HardwareVersion": safe_get(dev, ["Device", "DeviceInfo", "HardwareVersion"]),
        "Manufacturer": safe_get(dev, ["Device", "DeviceInfo", "Manufacturer"]),
        "UptimeTR069": safe_get(dev, ["Device", "DeviceInfo", "UpTime"]),
    }

    # ACS
    acs = {
        "ACS_URL": safe_get(dev, ["Device", "ManagementServer", "URL"]),
        "NATDetected": safe_get(dev, ["Device", "ManagementServer", "NATDetected"]),
        "PeriodicInformInterval": safe_get(dev, ["Device", "ManagementServer", "PeriodicInformInterval"]),
    }

    # System
    last_boot = dev.get("_lastBoot")
    uptime = calculate_uptime_from_lastboot(last_boot)

    # 🔥 S1 STATUS (COM FALLBACK)
    s1_status = get_first_valid(dev, [
        ["Device","Services","FAPService","1","FAPControl","LTE","Gateway","X_681D64_S1Status"],
        ["Device","Services","FAPService","1","FAPControl","LTE","X_BBU_S1Status"],
        ["Device","Services","FAPService","1","FAPControl","LTE","S1Status"],
    ])

    # 🔥 SUMMARY FINAL
    summary = {
        "ModelName": device_info.get("ModelName"),

        "S1Status": s1_status,

        "UeNumber": safe_get(dev, [
            "Device", "Services", "FAPService", "1",
            "FAPControl", "LTE", "UeNumberOfEntries"
        ]) or 0,

        "AlarmCount": safe_get(dev, [
            "Device", "Services", "FAPService", "1",
            "FAPControl", "LTE", "Alarm", "CurrentAlarmNumberOfEntries"
        ]) or 0,

        "Uptime": uptime,

        "UltimoInforme": dev.get("_lastInform") or "unknown",
        "Reboot": last_boot,

        "SerialNumber": device_info.get("SerialNumber"),
        "SoftwareVersion": device_info.get("SoftwareVersion"),
        "HardwareVersion": device_info.get("HardwareVersion"),

        "3GPPSpecVersion": "Release13",

        "Manufacturer": device_info.get("Manufacturer") or "SUNWAVE",

        "ACS_URL": acs.get("ACS_URL"),
        "PeriodicInformInterval": acs.get("PeriodicInformInterval"),
        "NATDetected": acs.get("NATDetected"),

        "CurrentAlarm": safe_get(dev, [
            "Device", "Services", "FAPService", "1",
            "FAPControl", "LTE", "Alarm", "CurrentAlarmNumberOfEntries"
        ]) or 0
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

