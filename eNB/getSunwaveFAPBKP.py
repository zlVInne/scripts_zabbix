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
            "Device.DeviceInfo.ActiveCellNumber",
            "Device.DeviceInfo.ModelName",
            "Device.DeviceInfo.SerialNumber",
            "Device.DeviceInfo.SoftwareVersion",
            "Device.DeviceInfo.HardwareVersion",
            "Device.DeviceInfo.X_BBU_KernelVersion",

            # IP
            "Device.IP.LANIpAddr",
            "Device.IP.Interface.1.IPv4Address.1.IPAddress",

            # ACS
            "Device.ManagementServer.URL",
            "Device.ManagementServer.NATDetected",

            # ENB
            "Device.Services.X_BBU_ENB.ENBID",

            # RRU
            "Device.Services.X_BBU_RU2460NODE.1.ConnectStatus",
            "Device.Services.X_BBU_RU2460NODE.1.RRUType",
            "Device.Services.X_BBU_RU2460NODE.1.RRUSoftwareVersion",
            "Device.Services.X_BBU_RU2460NODE.1.ProductionSerialNumber",
            "Device.Services.X_BBU_RU2460NODE.1.CH1DLOutputPower",
            "Device.Services.X_BBU_RU2460NODE.1.CH2DLOutputPower",
            "Device.Services.X_BBU_RU2460NODE.1.CH1ULInputPower",
            "Device.Services.X_BBU_RU2460NODE.1.CH2ULInputPower",

            # CELL 1
            "Device.Services.FAPService.1.CellConfig.LTE.RAN.Common.CellIdentity",
            "Device.Services.FAPService.1.CellConfig.LTE.RAN.RF.PhyCellID",
            "Device.Services.FAPService.1.CellConfig.LTE.RAN.RF.EARFCNDL",
            "Device.Services.FAPService.1.CellConfig.LTE.RAN.RF.EARFCNUL",
            "Device.Services.FAPService.1.CellConfig.LTE.RAN.RF.DLBandwidth",
            "Device.Services.FAPService.1.CellConfig.LTE.RAN.RF.ULBandwidth",
            "Device.Services.FAPService.1.FAPControl.LTE.X_BBU_CellStatus",
            "Device.Services.FAPService.1.FAPControl.LTE.X_BBU_S1Status",

            # CELL 2
            "Device.Services.FAPService.2.CellConfig.LTE.RAN.Common.CellIdentity",
            "Device.Services.FAPService.2.FAPControl.LTE.X_BBU_CellStatus",
            "Device.Services.FAPService.2.FAPControl.LTE.X_BBU_S1Status",

            # CELL 3
            "Device.Services.FAPService.3.CellConfig.LTE.RAN.Common.CellIdentity",
            "Device.Services.FAPService.3.FAPControl.LTE.X_BBU_CellStatus",
            "Device.Services.FAPService.3.FAPControl.LTE.X_BBU_S1Status",
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


# 🔥 UPTIME baseado no _lastBoot
def calculate_uptime_from_lastboot(last_boot):
    if not last_boot:
        return None

    try:
        bt = datetime.fromisoformat(last_boot.replace("Z", "+00:00"))
    except:
        return None

    now = datetime.now(timezone.utc)
    return int((now - bt).total_seconds())


def get_cell(dev, idx):
    base = ["Device", "Services", "FAPService", str(idx)]

    return {
        "CellIdentity": safe_get(dev, base + ["CellConfig", "LTE", "RAN", "Common", "CellIdentity"]),
        "PCI": safe_get(dev, base + ["CellConfig", "LTE", "RAN", "RF", "PhyCellID"]),
        "DL_EARFCN": safe_get(dev, base + ["CellConfig", "LTE", "RAN", "RF", "EARFCNDL"]),
        "UL_EARFCN": safe_get(dev, base + ["CellConfig", "LTE", "RAN", "RF", "EARFCNUL"]),
        "DL_BW": safe_get(dev, base + ["CellConfig", "LTE", "RAN", "RF", "DLBandwidth"]),
        "UL_BW": safe_get(dev, base + ["CellConfig", "LTE", "RAN", "RF", "ULBandwidth"]),
        "CellStatus": safe_get(dev, base + ["FAPControl", "LTE", "X_BBU_CellStatus"]),
        "S1Status": safe_get(dev, base + ["FAPControl", "LTE", "X_BBU_S1Status"]),
    }


def main():
    refresh_parameters()
    time.sleep(8)

    dev = get_device()

    # DeviceInfo
    device_info = {
        "ActiveCellNumber": safe_get(dev, ["Device", "DeviceInfo", "ActiveCellNumber"]),
        "ModelName": safe_get(dev, ["Device", "DeviceInfo", "ModelName"]),
        "SerialNumber": safe_get(dev, ["Device", "DeviceInfo", "SerialNumber"]),
        "SoftwareVersion": safe_get(dev, ["Device", "DeviceInfo", "SoftwareVersion"]),
        "HardwareVersion": safe_get(dev, ["Device", "DeviceInfo", "HardwareVersion"]),
        "KernelVersion": safe_get(dev, ["Device", "DeviceInfo", "X_BBU_KernelVersion"]),
    }

    # Network
    network = {
        "LAN_IP": safe_get(dev, ["Device", "IP", "LANIpAddr"]),
        "S1_IP": safe_get(dev, ["Device", "IP", "Interface", "1", "IPv4Address", "1", "IPAddress"]),
    }

    # ACS
    acs = {
        "ACS_URL": safe_get(dev, ["Device", "ManagementServer", "URL"]),
        "NATDetected": safe_get(dev, ["Device", "ManagementServer", "NATDetected"]),
    }

    # ENB
    enb = {
        "ENBID": safe_get(dev, ["Device", "Services", "X_BBU_ENB", "ENBID"])
    }

    # RRU
    rru = {
        "Status": safe_get(dev, ["Device", "Services", "X_BBU_RU2460NODE", "1", "ConnectStatus"]),
        "Type": safe_get(dev, ["Device", "Services", "X_BBU_RU2460NODE", "1", "RRUType"]),
        "Version": safe_get(dev, ["Device", "Services", "X_BBU_RU2460NODE", "1", "RRUSoftwareVersion"]),
        "ProductionSerialNumber": safe_get(dev, ["Device", "Services", "X_BBU_RU2460NODE", "1", "ProductionSerialNumber"]),
        "CH1_DL": safe_get(dev, ["Device", "Services", "X_BBU_RU2460NODE", "1", "CH1DLOutputPower"]),
        "CH2_DL": safe_get(dev, ["Device", "Services", "X_BBU_RU2460NODE", "1", "CH2DLOutputPower"]),
        "CH1_UL": safe_get(dev, ["Device", "Services", "X_BBU_RU2460NODE", "1", "CH1ULInputPower"]),
        "CH2_UL": safe_get(dev, ["Device", "Services", "X_BBU_RU2460NODE", "1", "CH2ULInputPower"]),
    }

    # 🔥 System usando _lastBoot
    last_boot = dev.get("_lastBoot")
    uptime = calculate_uptime_from_lastboot(last_boot)

    system = {
        "Boot": last_boot,
        "UptimeSeconds": uptime
    }

    # Cells
    cells = {}
    active_cells = device_info["ActiveCellNumber"] or 0

    for i in range(1, int(active_cells) + 3):
        cell = get_cell(dev, i)
        if any(cell.values()):
            cells[f"Cell_{i}"] = cell

    result = {
        "DeviceInfo": device_info,
        "Network": network,
        "ACS": acs,
        "ENB": enb,
        "RRU": rru,
        "Cells": cells,
        "System": system,
        "LastInform": dev.get("_lastInform"),
        "LastBoot": dev.get("_lastBoot")
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

