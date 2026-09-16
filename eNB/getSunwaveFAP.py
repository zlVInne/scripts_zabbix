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
    
    # Usamos refreshObject nos nós principais.
    # Isso garante que o ACS leia dinamicamente múltiplas células e rádios sem precisarmos "adivinhar" os índices.
    payloads = [
        {"name": "refreshObject", "objectName": "Device.DeviceInfo"},
        {"name": "refreshObject", "objectName": "Device.ManagementServer"},
        {"name": "refreshObject", "objectName": "Device.IP"},
        {"name": "refreshObject", "objectName": "Device.Services.X_BBU_ENB"},
        {"name": "refreshObject", "objectName": "Device.Services.FAPService"},
        {"name": "refreshObject", "objectName": "Device.Services.X_BBU_RU2460NODE"}
    ]

    try:
        for p in payloads:
            requests.post(url, json=p, timeout=5)
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


# Função auxiliar para pegar o nó inteiro (dicionário) e iterar sobre ele
def safe_get_node(d, path):
    try:
        for p in path:
            d = d[p]
        return d
    except:
        return {}


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


def main():
    refresh_parameters()
    time.sleep(8)

    dev = get_device()

    # 1. DeviceInfo (Seu original + Adições)
    device_info = {
        "Manufacturer": safe_get(dev, ["Device", "DeviceInfo", "Manufacturer"]) or "SUNWAVE",
        "ActiveCellNumber": safe_get(dev, ["Device", "DeviceInfo", "ActiveCellNumber"]),
        "ModelName": safe_get(dev, ["Device", "DeviceInfo", "ModelName"]),
        "SerialNumber": safe_get(dev, ["Device", "DeviceInfo", "SerialNumber"]),
        "SoftwareVersion": safe_get(dev, ["Device", "DeviceInfo", "SoftwareVersion"]),
        "HardwareVersion": safe_get(dev, ["Device", "DeviceInfo", "HardwareVersion"]),
        "KernelVersion": safe_get(dev, ["Device", "DeviceInfo", "X_BBU_KernelVersion"]),
        "BoardTemperature": safe_get(dev, ["Device", "DeviceInfo", "X_BBU_BOARDTEMP"])
    }

    # 2. Network (Seu original)
    network = {
        "LAN_IP": safe_get(dev, ["Device", "IP", "LANIpAddr"]),
        "S1_IP": safe_get(dev, ["Device", "IP", "Interface", "1", "IPv4Address", "1", "IPAddress"]),
    }

    # 3. ACS (Seu original)
    acs = {
        "ACS_URL": safe_get(dev, ["Device", "ManagementServer", "URL"]),
        "NATDetected": safe_get(dev, ["Device", "ManagementServer", "NATDetected"]),
    }

    # 4. ENB (Seu original)
    enb = {
        "ENBID": safe_get(dev, ["Device", "Services", "X_BBU_ENB", "ENBID"])
    }

    # 5. System (Seu original)
    last_boot = dev.get("_lastBoot")
    system = {
        "Boot": last_boot,
        "UptimeSeconds": calculate_uptime_from_lastboot(last_boot)
    }

    # ---------------------------------------------------------
    # 🔥 DESCOBERTA DINÂMICA DE CÉLULAS (Zabbix LLD)
    # ---------------------------------------------------------
    cells_list = []
    fap_service = safe_get_node(dev, ["Device", "Services", "FAPService"])
    
    for key, val in fap_service.items():
        if str(key).isdigit():  # Encontra os índices 1, 2, 3... dinamicamente
            cells_list.append({
                "CellIndex": key,
                # Dados Originais
                "CellIdentity": safe_get(val, ["CellConfig", "LTE", "RAN", "Common", "CellIdentity"]),
                "PCI": safe_get(val, ["CellConfig", "LTE", "RAN", "RF", "PhyCellID"]),
                "DL_EARFCN": safe_get(val, ["CellConfig", "LTE", "RAN", "RF", "EARFCNDL"]),
                "UL_EARFCN": safe_get(val, ["CellConfig", "LTE", "RAN", "RF", "EARFCNUL"]),
                "DL_BW": safe_get(val, ["CellConfig", "LTE", "RAN", "RF", "DLBandwidth"]),
                "UL_BW": safe_get(val, ["CellConfig", "LTE", "RAN", "RF", "ULBandwidth"]),
                "CellStatus": safe_get(val, ["FAPControl", "LTE", "X_BBU_CellStatus"]),
                "S1Status": safe_get(val, ["FAPControl", "LTE", "X_BBU_S1Status"]) or safe_get(val, ["FAPControl", "LTE", "S1Status"]),
                
                # Dados Adicionados (V2)
                "TAC": safe_get(val, ["CellConfig", "LTE", "EPC", "TAC"]),
                "PLMNID": safe_get(val, ["CellConfig", "LTE", "EPC", "PLMNList", "1", "PLMNID"]),
                "AdminState": safe_get(val, ["FAPControl", "LTE", "AdminState"]),
                "MaxTxPower": safe_get(val, ["CellConfig", "LTE", "RAN", "RF", "X_BBU_MaxTxPower"]),
                "UeNumber": safe_get(val, ["FAPControl", "LTE", "UeNumberOfEntries"]) or 0,
            })

    # ---------------------------------------------------------
    # 🔥 DESCOBERTA DINÂMICA DE RRUs (Zabbix LLD)
    # ---------------------------------------------------------
    rrus_list = []
    ru_node = safe_get_node(dev, ["Device", "Services", "X_BBU_RU2460NODE"])
    
    for key, val in ru_node.items():
        if str(key).isdigit():
            rrus_list.append({
                "RRUIndex": key,
                # Dados Originais
                "Status": safe_get(val, ["ConnectStatus"]),
                "Type": safe_get(val, ["RRUType"]) or safe_get(val, ["Type"]),
                "Version": safe_get(val, ["RRUSoftwareVersion"]) or safe_get(val, ["SoftwareVersion"]),
                "ProductionSerialNumber": safe_get(val, ["ProductionSerialNumber"]),
                "CH1_DL": safe_get(val, ["CH1DLOutputPower"]),
                "CH2_DL": safe_get(val, ["CH2DLOutputPower"]),
                "CH1_UL": safe_get(val, ["CH1ULInputPower"]),
                "CH2_UL": safe_get(val, ["CH2ULInputPower"]),
                
                # Dados Adicionados (V2)
                "CH1_Attenuation": safe_get(val, ["CH1DLPowerAttenuationValue"]),
                "CH2_Attenuation": safe_get(val, ["CH2DLPowerAttenuationValue"]),
            })

    # Construção do JSON Final mantendo sua hierarquia
    result = {
        "DeviceInfo": device_info,
        "Network": network,
        "ACS": acs,
        "ENB": enb,
        "System": system,
        "Cells": cells_list,    # Agora é um array dinâmico
        "RRUs": rrus_list,      # Agora é um array dinâmico
        "LastInform": dev.get("_lastInform"),
        "LastBoot": dev.get("_lastBoot")
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
