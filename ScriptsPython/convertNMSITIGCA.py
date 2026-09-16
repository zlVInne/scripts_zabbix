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

        # Ignorar cabeçalhos e coisas que não importam
        if not linha or linha.startswith(("VECTURA", "ITRASE:", "INTERROGACAO", "RESPOSTA", "----")):
            continue

        # Novo bloco inicia com IGR =
        if linha.startswith("IGR ="):
            # Se já existe um bloco anterior, salva antes de iniciar outro
            if bloco:
                if periodos:
                    bloco["PERIODOS"] = periodos
                resultados.append(bloco)

            bloco = {"IGR": int(linha.split("=")[1].strip())}
            periodos = []
            continue

        # Linhas de períodos (1 147 9, etc.)
        if re.match(r"^\d+\s+\d+\s+\d+", linha):
            partes = linha.split()
            periodos.append({
                "PERIODO": int(partes[0]),
                "TOTAL_SESSOES": int(partes[1]),
                "MAX_SIMULTANEAS": int(partes[2])
            })
            continue

        # Linha MAX ATINGIDO
        if linha.startswith("MAX ATINGIDO"):
            partes = linha.split()
            bloco["MAX_ATINGIDO"] = {
                "TOTAL_SESSOES": int(partes[-2]),
                "MAX_SIMULTANEAS": int(partes[-1])
            }
            continue

# Salvar último bloco se existir
if bloco:
    if periodos:
        bloco["PERIODOS"] = periodos
    resultados.append(bloco)

# JSON compacto (sem espaços nem indentação)
print(json.dumps(resultados, ensure_ascii=False, separators=(",", ":")))

