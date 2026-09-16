#!/usr/bin/env python3
import json
import sys
import os
import re

if len(sys.argv) != 2:
    print(f"Uso: {sys.argv[0]} <arquivo>")
    sys.exit(1)

arq = sys.argv[1]

if not os.path.isfile(arq):
    print(f"Arquivo '{arq}' não encontrado.")
    sys.exit(1)

resultado = {
    "FRC": [],
    "STATUS_CELULA": None,
    "PROCESSADORES": []
}

with open(arq, "r", encoding="utf-8") as f:
    for linha in f:
        linha = linha.strip()

        if not linha:
            continue

        # Captura FRC (pode ter mais de um)
        if linha.startswith("FRC"):
            partes = linha.split("=")
            if len(partes) > 1:
                frc = partes[1].strip()
                resultado["FRC"].append(frc)

        # Captura status da célula (linha descritiva)
        elif "CELULA DE BILHETAGEM" in linha:
            resultado["STATUS_CELULA"] = linha

        # Captura processadores (dinâmico)
        elif "PROCESSADOR DA PLATAFORMA MBA" in linha:
            match = re.search(r"ESTADO\s+(.+?)\.*:\s*(\d+)", linha)
            if match:
                estado = match.group(1).strip()
                proc = int(match.group(2))

                resultado["PROCESSADORES"].append({
                    "ESTADO": estado,
                    "PROCESSADOR": proc
                })

print(json.dumps(resultado, ensure_ascii=False, indent=2))

