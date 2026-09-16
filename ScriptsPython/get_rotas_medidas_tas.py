#!/usr/bin/env python3
import subprocess
import json
import sys
import os
from datetime import datetime
import shutil

# ======= CONFIGURAÇÕES =======
USUARIO = "matuser"
PASSWORD = "matuser"   # ajuste conforme necessário
DIRETORIO_SAIDA = "/etc/zabbix/scripts"
# ==============================

# Verifica parâmetros
if len(sys.argv) != 2:
    print(f"Uso: {sys.argv[0]} <ip>")
    sys.exit(1)

IP = sys.argv[1]
SERVER = f"{USUARIO}@{IP}"

# Caminhos dos binários
DBCLIENT = shutil.which("dbclient")
if not DBCLIENT:
    print("dbclient não encontrado. Instale o Dropbear client.")
    sys.exit(1)

SSHPASS = shutil.which("sshpass")
if PASSWORD and not SSHPASS:
    print("sshpass não encontrado, necessário para senha automática.")
    sys.exit(1)

# Comandos SQL
SQL_ROTAS = 'select * from tab_rota_id;'
SQL_MEDIDAS = """select * from med_rotas
where data=CURRENT_DATE
and (data || ' ' || hora)::timestamp >= NOW() - INTERVAL '10 minutes';"""

# Colunas das medidas
COLUNAS = [
    "rota", "ofer_tra", "ocup_tra", "ocef_tra", "trto_tra", "tref_tra",
    "ofer_out", "ocup_out", "ocef_out", "trto_out", "tref_out",
    "data", "hora", "restricao", "bloq", "n_bloq", "n_ocup", "n_liv",
    "n_em_serv", "rota_sip"
]

# Função para executar comando SQL remoto usando Dropbear
def run_ssh_psql(sql, db):
    # ATUALIZADO: Removemos o -c "{sql}". O psql vai ler a query pela entrada padrão (stdin)
    remote_cmd = f'psql -h 127.0.0.1 -U postgres -d {db} -A -t -F","'

    # comando base
    cmd = [DBCLIENT, "-y", SERVER, remote_cmd]

    # se houver senha, adiciona sshpass
    if PASSWORD:
        cmd = [SSHPASS, "-p", PASSWORD] + cmd

    try:
        # ATUALIZADO: Passamos a variável sql no parâmetro input
        result = subprocess.run(cmd, input=sql, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print(f"[{IP}] Timeout ao conectar via dbclient")
        sys.exit(1)

    if result.returncode != 0:
        print(f"[{IP}] Erro ao executar SQL no banco '{db}': {result.stderr.strip()}")
        sys.exit(1)

    lines = [line for line in result.stdout.strip().split("\n") if line]
    return [line.split(",") for line in lines]

# Conversão segura
def to_float(v):
    try:
        return float(v)
    except:
        return 0.0

# ======= 1) Consultar dados =======
rotas = run_ssh_psql(SQL_ROTAS, "bmgcp")
medidas = run_ssh_psql(SQL_MEDIDAS, "medidas")
med_dict = {row[0].strip(): [x.strip() for x in row] for row in medidas}

json_list = []

# ======= 2) Calcular métricas =======
for rota in rotas:
    rota_id = rota[0].strip()
    nome = rota[1].strip().replace(".", "_")

    if rota_id in med_dict:
        valores = med_dict[rota_id][1:]
    else:
        valores = ["0"]*19 + [""]

    entry = {"ip": IP, "rota": nome}
    for col_name, val in zip(COLUNAS[1:], valores):
        entry[col_name] = val.strip() if isinstance(val, str) else val

    # === Cálculos das métricas ===
    ofer_tra = to_float(entry["ofer_tra"])
    ocup_tra = to_float(entry["ocup_tra"])
    ocef_tra = to_float(entry["ocef_tra"])
    trto_tra = to_float(entry["trto_tra"])
    tref_tra = to_float(entry["tref_tra"])
    ofer_out = to_float(entry["ofer_out"])
    ocup_out = to_float(entry["ocup_out"])
    ocef_out = to_float(entry["ocef_out"])
    trto_out = to_float(entry["trto_out"])
    tref_out = to_float(entry["tref_out"])
    bloq = to_float(entry["bloq"])
    n_em_serv = to_float(entry["n_em_serv"])

    recurso = ofer_tra - ocup_tra
    erro_recurso = recurso > 1
    porcentagemOK = (ocef_tra / ofer_tra * 100) if ofer_tra > 0 else 0
    erro_porcentagemOK = porcentagemOK < 45 and ofer_tra > 0
    TMRE = (tref_tra / ocef_tra) if ocef_tra > 0 else 0
    erro_TMRE = TMRE < 60 and ocef_tra > 0
    PJS = (bloq / n_em_serv * 100) if n_em_serv > 0 else 0
    status_PJS = "OK"
    if PJS >= 50:
        status_PJS = "Major"
    elif PJS >= 25:
        status_PJS = "Minor"
    trafego_total_erl = (trto_tra + trto_out) / (5*60)
    trafego_efic_erl = (tref_tra + tref_out) / (5*60)

    entry.update({
        "recurso": round(recurso,2),
        "erro_recurso": erro_recurso,
        "porcentagemOK": round(porcentagemOK,2),
        "erro_porcentagemOK": erro_porcentagemOK,
        "TMRE": round(TMRE,2),
        "erro_TMRE": erro_TMRE,
        "PJS": round(PJS,2),
        "status_PJS": status_PJS,
        "trafego_total_erl": round(trafego_total_erl,2),
        "trafego_efic_erl": round(trafego_efic_erl,2)
    })
    json_list.append(entry)

# ======= 3) Salvar JSON detalhado =======
os.makedirs(DIRETORIO_SAIDA, exist_ok=True)
arq_metricas = os.path.join(DIRETORIO_SAIDA, f"json_metricas_rotas_{IP}.json")
with open(arq_metricas, "w") as f:
    json.dump(json_list, f, ensure_ascii=False, separators=(",", ":"))
print(f"[{IP}] JSON de métricas salvo em {arq_metricas}")

# ======= 4) Gerar JSON resumo =======
total_rotas = len(json_list)
if total_rotas > 0:
    soma = {
        "recurso":0, "porcentagemOK":0, "TMRE":0,
        "PJS":0, "trafego_total_erl":0, "trafego_efic_erl":0
    }
    erros = {"equipamento_sem_recurso":0, "porcentagemOK_baixa":0, "TMRE_baixo":0}
    status = {"major":0, "minor":0}

    for r in json_list:
        soma["recurso"] += r.get("recurso",0)
        soma["porcentagemOK"] += r.get("porcentagemOK",0)
        soma["TMRE"] += r.get("TMRE",0)
        soma["PJS"] += r.get("PJS",0)
        soma["trafego_total_erl"] += r.get("trafego_total_erl",0)
        soma["trafego_efic_erl"] += r.get("trafego_efic_erl",0)

        if r.get("erro_recurso"): erros["equipamento_sem_recurso"] +=1
        if r.get("erro_porcentagemOK"): erros["porcentagemOK_baixa"] +=1
        if r.get("erro_TMRE"): erros["TMRE_baixo"] +=1

        if r.get("status_PJS")=="Major": status["major"] +=1
        elif r.get("status_PJS")=="Minor": status["minor"] +=1

    resumo = {
        "ip": IP,
        "data_coleta": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_rotas": total_rotas,
        "media_recurso": round(soma["recurso"]/total_rotas,2),
        "media_porcentagemOK": round(soma["porcentagemOK"]/total_rotas,2),
        "media_TMRE": round(soma["TMRE"]/total_rotas,2),
        "media_PJS": round(soma["PJS"]/total_rotas,2),
        "media_trafego_total_erl": round(soma["trafego_total_erl"]/total_rotas,2),
        "media_trafego_efic_erl": round(soma["trafego_efic_erl"]/total_rotas,2),
        "erros": erros,
        "status_PJS": status
    }

    arq_resumo = os.path.join(DIRETORIO_SAIDA, f"json_resumo_rotas_{IP}.json")
    with open(arq_resumo,"w") as f:
        json.dump(resumo,f,ensure_ascii=False,separators=(",",":"))
    print(f"[{IP}] JSON de resumo salvo em {arq_resumo}")
else:
    print(f"[{IP}] Nenhuma rota encontrada para gerar resumo.")
