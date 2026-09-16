#!/usr/bin/env python3

import json
import re
import sys
from collections import defaultdict

# =========================================================
# Uso:
#   python3 parse_ilogce.py arquivo.txt
#
# Objetivo:
#   Contar quantas vezes cada comando foi executado
#   agrupando por usuário.
#
# Saída:
#
# [
#   {
#     "usuario": "SISTEMA",
#     "comandos": [
#       {
#         "comando": "SARQMM:ARQ=\"ICHASI.RCC\";",
#         "quantidade": 68
#       }
#     ]
#   }
# ]
#
# =========================================================

if len(sys.argv) != 2:
    print(f"Uso: {sys.argv[0]} <arquivo>")
    sys.exit(1)

arquivo = sys.argv[1]

try:
    with open(arquivo, "r", encoding="utf-8") as f:
        linhas = f.readlines()

except FileNotFoundError:
    print(f"Arquivo não encontrado: {arquivo}")
    sys.exit(1)

# =========================================================
# Regex do cabeçalho
#
# Exemplo:
#
# 2026-5-11      0:05:03       SISTEMA
#
# =========================================================

regex_header = re.compile(
    r'^(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2}:\d{2})\s+(.+)$'
)

# =========================================================
# Estrutura:
#
# {
#   "SISTEMA": {
#       "COMANDO1": 10,
#       "COMANDO2": 20
#   }
# }
#
# =========================================================

resultado = defaultdict(lambda: defaultdict(int))

i = 0

while i < len(linhas):

    linha = linhas[i].strip()

    match = regex_header.match(linha)

    if match:

        data = match.group(1)
        hora = match.group(2)
        usuario = match.group(3).strip()

        # Padroniza usuário
        usuario = usuario.upper()

        # Próxima linha deve conter o comando
        if i + 1 < len(linhas):

            comando = linhas[i + 1].strip()

            # Ignora linhas vazias
            if comando:

                # Remove espaços duplicados
                comando = re.sub(r'\s+', ' ', comando)

                # Padroniza comando
                comando = comando.upper()

                # Soma quantidade
                resultado[usuario][comando] += 1

        i += 2

    else:
        i += 1

# =========================================================
# Monta saída estruturada
# =========================================================

saida = []

for usuario, comandos in resultado.items():

    item_usuario = {
        "usuario": usuario,
        "comandos": []
    }

    for comando, quantidade in comandos.items():

        item_usuario["comandos"].append({
            "comando": comando,
            "quantidade": quantidade
        })

    # Ordena comandos por quantidade (maior -> menor)
    item_usuario["comandos"] = sorted(
        item_usuario["comandos"],
        key=lambda x: x["quantidade"],
        reverse=True
    )

    saida.append(item_usuario)

# Ordena usuários alfabeticamente
saida = sorted(saida, key=lambda x: x["usuario"])

# =========================================================
# Print JSON final
# =========================================================
print(json.dumps(saida, ensure_ascii=False))
