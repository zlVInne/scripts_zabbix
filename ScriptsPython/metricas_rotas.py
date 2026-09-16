#!/usr/bin/env python3
import json
import sys
import os

# Verifica parâmetro
if len(sys.argv) != 2:
    print(f"Uso: {sys.argv[0]} <arquivo_json_entrada>")
    sys.exit(1)

arquivo_entrada = sys.argv[1]

# Verifica se o arquivo existe
if not os.path.exists(arquivo_entrada):
    print(f"Erro: arquivo {arquivo_entrada} não encontrado.")
    sys.exit(1)

# Carregar o JSON original
with open(arquivo_entrada, "r", encoding="utf-8") as f:
    rotas = json.load(f)

metricas = []

for r in rotas:
    try:
        ofer_tra = int(r["ofer_tra"])
        ocup_tra = int(r["ocup_tra"])
        ocef_tra = int(r["ocef_tra"])
        trto_tra = int(r["trto_tra"])
        tref_tra = int(r["tref_tra"])
        n_ocup = int(r["n_ocup"])
        n_em_serv = int(r["n_em_serv"])
        n_liv = int(r["n_liv"])
        bloq = int(r["bloq"])
    except (KeyError, ValueError):
        continue

    # Cálculos de métricas
    taxa_ocupacao = (ocup_tra / ofer_tra * 100) if ofer_tra > 0 else 0
    taxa_sucesso = (tref_tra / trto_tra * 100) if trto_tra > 0 else 0
    uso_capacidade = (n_ocup / n_em_serv * 100) if n_em_serv > 0 else 0

    metricas.append({
        "rota": r["rota"].strip(),
        "ofertas_trafego": ofer_tra,
        "ocupacao_trafego": ocup_tra,
        "taxa_ocupacao_percent": round(taxa_ocupacao, 2),
        "chamadas_efetivas": ocef_tra,
        "tentativas": trto_tra,
        "completadas": tref_tra,
        "taxa_sucesso_percent": round(taxa_sucesso, 2),
        "em_uso": n_ocup,
        "livres": n_liv,
        "capacidade_total": n_em_serv,
        "uso_capacidade_percent": round(uso_capacidade, 2),
        "bloqueios": bloq,
        "rota_sip": r["rota_sip"]
    })

# Printar JSON compactado
print(json.dumps(metricas, separators=(',', ':')))

