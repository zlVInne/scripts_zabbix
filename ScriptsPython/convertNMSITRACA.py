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
bloco = None
periodos = []

with open(arq, "r", encoding="utf-8") as f:
    for linha in f:
        linha = linha.strip()

        if not linha or linha.startswith(("VECTURA", "ITRASE:", "INTERROGACAO", "RESPOSTA", "----")):
            continue

        # Novo bloco PRO
        if linha.startswith("PRO ="):
            # Se já existe bloco em andamento, salva e inicia outro
            if bloco:
                if periodos:
                    bloco["PERIODOS"] = periodos
                resultados.append(bloco)

            bloco = {"PRO": int(linha.split("=")[1].strip())}
            periodos = []
            continue

        # Linhas de períodos (ex: "  1   1485   198")
        if re.match(r"^\d+\s+\d+\s+\d+", linha):
            partes = linha.split()
            if len(partes) >= 3:
                periodos.append({
                    "PERIODO": int(partes[0]),
                    "TOTAL_SESSOES": int(partes[1]),
                    "MAX_SIMULTANEAS": int(partes[2])
                })
            continue

        # Linha do MAX ATINGIDO
        if linha.startswith("MAX ATINGIDO"):
            partes = linha.split()
            if len(partes) >= 3:
                bloco["MAX_ATINGIDO"] = {
                    "TOTAL_SESSOES": int(partes[-2]),
                    "MAX_SIMULTANEAS": int(partes[-1])
                }
            continue

# Salva último bloco
if bloco:
    if periodos:
        bloco["PERIODOS"] = periodos
    resultados.append(bloco)

print(json.dumps(resultados, ensure_ascii=False, separators=(",", ":")))

