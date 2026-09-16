#!/usr/bin/env python3
import json
import sys
import os

# Verifica se o argumento foi passado
if len(sys.argv) != 2:
    print(f"Uso: {sys.argv[0]} <arquivo>")
    sys.exit(1)

# Nome do arquivo recebido no argumento
arq = sys.argv[1]

try:
    with open(arq, "r", encoding="utf-8") as f:
        lines = f.readlines()
except FileNotFoundError:
    print(f"Arquivo não encontrado: {arq}")
    sys.exit(1)

header = None
values = None

for i, line in enumerate(lines):
    if line.strip().startswith("TRAFEGO -"):
        # remove o "TRAFEGO -" e pega o cabeçalho
        header = line.replace("TRAFEGO -", "").split()
        # a próxima linha são os valores
        if i + 1 < len(lines):
            values = lines[i+1].split()
        break

if header and values:
    data = dict(zip(header, values))
    print(json.dumps(data, indent=2, ensure_ascii=False))
else:
    print("Não foi possível encontrar os dados.")

