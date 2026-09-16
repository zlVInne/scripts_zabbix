import time
import os
import re
import json

RAW_LOG = '/var/log/snmptrap/snmptrap.log'
JSON_LOG = '/var/log/snmptrap/zabbix_json.log'

alarmes_ativos = {}

def extrair_dado(padrao, texto):
    match = re.search(padrao, texto)
    return match.group(1) if match else ""

def processar_linha(linha):
    if "enterprises.9635." not in linha:
        return

    try:
        # Extrai o IP e o Timestamp da massa bruta
        ip_match = re.search(r'UDP:\s+\[([0-9\.]+)\]', linha)
        ip = ip_match.group(1) if ip_match else "0.0.0.0"
        
        ts_match = re.match(r'^(\d+)', linha)
        ts = ts_match.group(1) if ts_match else str(int(time.time()))

        # Extrai as informações da Trap
        unique_id = extrair_dado(r'9635\.1\.1\.1\.1\.1\.2\.0\s+"([^"]+)"', linha)
        falha = extrair_dado(r'9635\.1\.1\.1\.1\.1\.3\.0\s+"([^"]+)"', linha)
        vus = extrair_dado(r'9635\.1\.1\.1\.1\.1\.4\.0\s+"VUS=\s*([^"]+)"', linha)
        proc = extrair_dado(r'9635\.1\.1\.1\.1\.1\.5\.0\s+(\d+)', linha)
        oco = extrair_dado(r'9635\.1\.1\.1\.1\.1\.6\.0\s+(\d+)', linha)
        nivel = extrair_dado(r'9635\.1\.1\.1\.1\.1\.9\.0\s+(\d+)', linha)
        psi = extrair_dado(r'9635\.1\.1\.1\.1\.1\.13\.0\s+(\d+)', linha)
        causa = extrair_dado(r'9635\.1\.1\.1\.1\.1\.19\.0\s+"([^"]+)"', linha)

        if not unique_id:
            return

        pacote = {
            "id": unique_id.strip(),
            "falha": falha,
            "proc": proc,
            "vus": vus,
            "psi": psi,
            "oco": oco,
            "nivel": nivel,
            "causa": causa
        }

        # A Lógica do Escudo Anti-Flood
        if oco == "0": 
            if unique_id not in alarmes_ativos:
                alarmes_ativos[unique_id] = True
                escrever_json(ts, ip, pacote)
        elif oco == "1":
            if unique_id in alarmes_ativos:
                del alarmes_ativos[unique_id]
            escrever_json(ts, ip, pacote)

    except Exception as e:
        print(f"Erro: {e}")

def escrever_json(ts, ip, dados):
    # Formato MÁGICO que o Zabbix exige para achar o Host
    linha_json = f"{ts} ZBXTRAP {ip} {json.dumps(dados)}\n"
    with open(JSON_LOG, 'a') as f:
        f.write(linha_json)

def seguir_arquivo(caminho):
    with open(caminho, 'r') as arquivo:
        arquivo.seek(0, os.SEEK_END)
        while True:
            linha = arquivo.readline()
            if not linha:
                time.sleep(0.1)
                continue
            processar_linha(linha)

if __name__ == '__main__':
    seguir_arquivo(RAW_LOG)
