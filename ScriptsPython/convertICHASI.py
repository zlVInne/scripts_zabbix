#!/usr/bin/env python3
import json
import sys
import os
import re

# Verifica se o argumento foi passado
if len(sys.argv) != 2:
    print(f"Uso: {sys.argv[0]} <arquivo>")
    sys.exit(1)


arquivo = sys.argv[1]

resultado = []

ccip_atual = None
ccip_obj = None

# Regex para linhas com dados de TPSIP
linha_re = re.compile(r'^\s*(\d+)?\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$')

with open(arquivo, 'r') as f:
    for linha in f:
        linha = linha.rstrip()
        match = linha_re.match(linha)
        if match:
            ccip, tpsip, ocupado, ocup_sai, ocup_ent = match.groups()
            # Se houver CCIP na linha, atualiza
            if ccip:
                ccip_atual = ccip
                # Cria novo objeto CCIP
                ccip_obj = {"CCIP": ccip_atual, "TPS": []}
                resultado.append(ccip_obj)
            # Adiciona TPSIP atual ao CCIP em contexto
            if ccip_obj is not None:
                ccip_obj["TPS"].append({
                    "TPSIP": tpsip,
                    "OCUPADO": ocupado,
                    "OCUP-SAI": ocup_sai,
                    "OCUP-ENT": ocup_ent
                })

# Saída JSON em linha única
json_saida = json.dumps(resultado, separators=(',', ':'))
print(json_saida)

