#!/usr/bin/env python3
import json
import sys
import re
import os

if len(sys.argv) != 2:
    print(f"Uso: {sys.argv[0]} <arquivo>")
    sys.exit(1)

arq = sys.argv[1]

if not os.path.isfile(arq):
    print(f"Arquivo '{arq}' não encontrado.")
    sys.exit(1)

rotas = []
rota_atual = {}

with open(arq, "r", encoding="utf-8") as f:
    for linha in f:
        linha = linha.strip()
        if not linha or linha.startswith(("REDIRECIONAMENTO", "VECTURA", "IDADRO:", "INTERROGACAO")):
            continue

        # Novo bloco ROT
        if linha.startswith("ROT ="):
            # Salva bloco anterior (se houver)
            if rota_atual:
                rotas.append(rota_atual)
                rota_atual = {}

            # Extrai ROT e o restante da linha
            partes = linha.split()
            rota_atual["ROT"] = int(partes[2])  # ROT = N
            # Pode haver outro par na mesma linha (ex: IRO = xxx)
            resto = " ".join(partes[3:])
            if resto:
                for match in re.finditer(r"(\w+)\s*=\s*([^\s]+)", resto):
                    chave, valor = match.groups()
                    rota_atual[chave] = valor
        else:
            # Processa pares chave=valor
            for match in re.finditer(r"(\w+)\s*=\s*([^\s]+)", linha):
                chave, valor = match.groups()
                # Converte números quando possível
                if valor.isdigit():
                    valor = int(valor)
                rota_atual[chave] = valor

# Adiciona último bloco
if rota_atual:
    rotas.append(rota_atual)

# Saída JSON compacta (1 linha)
print(json.dumps(rotas, ensure_ascii=False))

