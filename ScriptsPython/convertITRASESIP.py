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

resultados = []
bloco = {}
periodos = []

with open(arq, "r", encoding="utf-8") as f:
    for linha in f:
        linha = linha.strip()
        if not linha or linha.startswith(("REDIRECIONAMENTO", "VECTURA", "ITRASE:", "INTERROGACAO")):
            continue

        # Novo bloco PRO
        if linha.startswith("PRO ="):
            if bloco:
                if periodos:
                    bloco["PERIODOS"] = periodos
                resultados.append(bloco)
                bloco = {}
                periodos = []
            bloco["PRO"] = int(linha.split("=")[1].strip())

        elif linha.startswith("SESSOES ATIVAS"):
            bloco["SESSOES_ATIVAS"] = int(linha.split("=")[1].strip())
        elif linha.startswith("DIALOGOS ATIVOS"):
            bloco["DIALOGOS_ATIVOS"] = int(linha.split("=")[1].strip())
        elif re.match(r"^\d+\s+", linha):  # Linhas de períodos
            partes = linha.split()
            if len(partes) >= 4:
                periodos.append({
                    "PERIODO": int(partes[0]),
                    "SESSOES": int(partes[1]),
                    "DIALOGOS": int(partes[2]),
                    "MENSAGENS": int(partes[3])
                })
        elif linha.startswith("TOTAL") and not linha.startswith("TOTAL GERAL"):
            partes = linha.split()
            if len(partes) >= 4:
                bloco["TOTAL_SESSOES"] = int(partes[1])
                bloco["TOTAL_DIALOGOS"] = int(partes[2])
                bloco["TOTAL_MENSAGENS"] = int(partes[3])

# Último bloco
if bloco:
    if periodos:
        bloco["PERIODOS"] = periodos
    resultados.append(bloco)

# Procura TOTAL GERAL
with open(arq, "r", encoding="utf-8") as f:
    for linha in f:
        if linha.strip().startswith("TOTAL GERAL"):
            partes = linha.split()
            if len(partes) >= 5:
                resultados.append({
                    "PRO": "TOTAL_GERAL",
                    "SESSOES": int(partes[2]),
                    "DIALOGOS": int(partes[3]),
                    "MENSAGENS": int(partes[4])
                })

print(json.dumps(resultados, ensure_ascii=False, indent=2))

