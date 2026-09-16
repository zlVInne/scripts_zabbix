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

resultado = {}

with open(arq, "r", encoding="utf-8") as f:
    for linha in f:
        linha = linha.strip()

        if not linha:
            continue

        # PRO
        if linha.startswith("PRO"):
            resultado["PRO"] = int(linha.split("=")[1].strip())

        # DISPONIBIL.BLOCOS
        elif linha.startswith("DISPONIBIL.BLOCOS"):
            partes = linha.split(":")[1].split()
            resultado["BLOCOS"] = {
                "TOTAL": int(partes[0]),
                "LIVRES": int(partes[1]),
                "TRANSF": int(partes[2]),
                "NAO_TRANSF": int(partes[3])
            }

        # PERCENTUAL BLOCOS
        elif linha.startswith("PERCENTUAL BLOCOS"):
            partes = linha.split(":")[1].replace("%", "").split()
            resultado["PERCENTUAL_BLOCOS"] = {
                "TOTAL": float(partes[0].replace(",", ".")),
                "LIVRES": float(partes[1].replace(",", ".")),
                "TRANSF": float(partes[2].replace(",", ".")),
                "NAO_TRANSF": float(partes[3].replace(",", "."))
            }

        # DISPONIB.ARQUIVOS
        elif linha.startswith("DISPONIB.ARQUIVOS"):
            partes = linha.split(":")[1].split()
            resultado["ARQUIVOS"] = {
                "TOTAL": int(partes[0]),
                "LIVRES": int(partes[1]),
                "TRANSF": int(partes[2]),
                "NAO_TRANSF": int(partes[3])
            }

        # PERCENT. ARQUIVOS
        elif linha.startswith("PERCENT. ARQUIVOS"):
            partes = linha.split(":")[1].replace("%", "").split()
            resultado["PERCENTUAL_ARQUIVOS"] = {
                "TOTAL": float(partes[0].replace(",", ".")),
                "LIVRES": float(partes[1].replace(",", ".")),
                "TRANSF": float(partes[2].replace(",", ".")),
                "NAO_TRANSF": float(partes[3].replace(",", "."))
            }

        # LIMITES (NUR, SUR, URG)
        elif "LIM. DE NAO TRANSF" in linha:
            match = re.findall(r"(NUR|SUR|URG)\s*=\s*(\d+)", linha)
            limites = {}
            for k, v in match:
                limites[k] = int(v)
            resultado["LIMITES"] = limites

        # LIMITES ATINGIDOS
        elif linha.startswith("LIMITES ATINGIDOS"):
            partes = linha.split()
            resultado["LIMITES_ATINGIDOS"] = {
                "NUR": partes[2],
                "SUR": partes[3],
                "URG": partes[4]
            }
        # =========================
        # MÉTRICAS DERIVADAS
        # =========================

# Volume de CDRs (base: ARQUIVOS)
if "ARQUIVOS" in resultado:
    transf = resultado["ARQUIVOS"].get("TRANSF", 0)
    nao_transf = resultado["ARQUIVOS"].get("NAO_TRANSF", 0)

    resultado["Volume de CDRs"] = {
        "TRANSF": transf,
        "NAO_TRANSF": nao_transf,
        "TOTAL": transf + nao_transf
    }

# Quantidade de CDRs (base: BLOCOS)
if "BLOCOS" in resultado:
    transf = resultado["BLOCOS"].get("TRANSF", 0)
    nao_transf = resultado["BLOCOS"].get("NAO_TRANSF", 0)

    resultado["Quantidade de CDRs"] = {
        "TRANSF": transf,
        "NAO_TRANSF": nao_transf,
        "TOTAL": transf + nao_transf
    }

# Sucesso (base: NAO_TRANSF de ARQUIVOS)
if "ARQUIVOS" in resultado:
    resultado["Sucesso"] = {
        "NAO_TRANSF": resultado["ARQUIVOS"].get("NAO_TRANSF", 0)
    }


print(json.dumps(resultado, ensure_ascii=False, indent=2))

