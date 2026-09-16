#!/usr/bin/env python3
import json
import sys
import re
import os

# Verifica se o argumento foi passado
if len(sys.argv) != 2:
    print(f"Uso: {sys.argv[0]} <arquivo>")
    sys.exit(1)

# Nome do arquivo recebido no argumento
arq = sys.argv[1]

if not os.path.isfile(arq):
    print(f"Arquivo '{arq}' não encontrado.")
    sys.exit(1)

dados = []
with open(arq, "r", encoding="utf-8") as f:
    for linha in f:
        linha = linha.strip()
        # Pula cabeçalho e linhas não relevantes
        if not linha or \
           linha.startswith("VECTURA") or \
           linha.startswith("ILICCE:") or \
           linha.startswith("INTERROGACAO") or \
           linha.startswith("LICENCA") or \
           linha.startswith("REDIRECIONAMENTO"):
            continue

        # Regex: captura texto + dois valores no final (somente se forem numéricos, "-" ou "??")
        m = re.match(r"(.+?)\s+(\d+|[-\?]+)\s+(\d+|[-\?]+)$", linha)
        if m:
            licenca = m.group(1).strip()
            qtd_contratada = m.group(2).strip()
            qtd_utilizada = m.group(3).strip()

            dados.append({
                "LICENCA": licenca,
                "QTDE_CONTRATADA": qtd_contratada,
                "QTDE_UTILIZADA": qtd_utilizada
            })

# Imprime JSON em uma única linha
print(json.dumps(dados, ensure_ascii=False))

