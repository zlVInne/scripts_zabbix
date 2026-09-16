import paramiko
import re
import json
import time
import sys

USERNAME = "zabbixpmi"
PASSWORD = "Zabbix2025!"

REALMS = ["core"]

def connect_ssh(ip):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=USERNAME, password=PASSWORD)
    return ssh

def wait_for_prompt(shell, timeout=60):
    output = ""
    start_time = time.time()

    while True:
        if shell.recv_ready():
            chunk = shell.recv(65535).decode(errors="ignore")
            output += chunk

            if re.search(r"\n\S+[>#]\s?$", output):
                break

        if time.time() - start_time > timeout:
            print("Timeout aguardando prompt.")
            break

        time.sleep(0.5)

    return output

def run_command(shell, command):
    shell.send(command + "\n")
    return wait_for_prompt(shell)

def extract_register_stats_flat(output, realm):
    rows = []

    def parse_val(val):
        return int(val) if val.isdigit() else val

    # Extrai Latência e Burst Rate (Globais do Realm) para incluir nas colunas
    avg_lat = max_lat = burst_in = burst_out = None
    
    avg_lat_match = re.search(r"Avg Latency=([\d\.]+)", output)
    if avg_lat_match: avg_lat = float(avg_lat_match.group(1))

    max_lat_match = re.search(r"Max Latency=([\d\.]+)", output)
    if max_lat_match: max_lat = float(max_lat_match.group(1))

    burst_match = re.search(r"BurstRate Incoming=(\d+)\s+Outgoing=(\d+)", output)
    if burst_match:
        burst_in = int(burst_match.group(1))
        burst_out = int(burst_match.group(2))

    # Regex para extrair as linhas da tabela de mensagens
    table_pattern = re.compile(r"^([A-Za-z0-9\s]+?)\s+([\d\-]+)\s+([\d\-]+)\s+([\d\-]+)\s+([\d\-]+)\s+([\d\-]+)\s+([\d\-]+)\s*$", re.MULTILINE)

    for match in table_pattern.finditer(output):
        # Cada "match" vira uma linha na tabela do Grafana
        row = {
            "Realm": realm,
            "Message_Event": match.group(1).strip(),
            "Server_Recent": parse_val(match.group(2)),
            "Server_Total": parse_val(match.group(3)),
            "Server_PerMax": parse_val(match.group(4)),
            "Client_Recent": parse_val(match.group(5)),
            "Client_Total": parse_val(match.group(6)),
            "Client_PerMax": parse_val(match.group(7)),
            "Avg_Latency": avg_lat,
            "Max_Latency": max_lat,
            "Burst_Incoming": burst_in,
            "Burst_Outgoing": burst_out
        }
        rows.append(row)

    return rows

def main(ip):
    try:
        ssh = connect_ssh(ip)
        shell = ssh.invoke_shell()
        time.sleep(3)

        if shell.recv_ready():
            shell.recv(65535)

        wait_for_prompt(shell)

        # Agora teremos uma lista simples que será a raiz do JSON
        all_data_flat = []

        print(f"Coletando estatísticas SIP REGISTER do IP: {ip}...")

        for realm in REALMS:
            print(f"Consultando realm: {realm}")
            
            command = f"show sipd realms {realm} register"
            output = run_command(shell, command)
            
            # Adiciona as linhas retornadas à lista principal
            linhas = extract_register_stats_flat(output, realm)
            if linhas:
                all_data_flat.extend(linhas)
            else:
                print(f"  -> Nenhum dado encontrado para o realm {realm}")

    except Exception as e:
        print(f"Erro ao conectar ou executar comandos: {e}")
        return
    finally:
        ssh.close()

    if not all_data_flat:
        print("\nNenhuma estatística válida foi encontrada.")
        return

    nome_arquivo = f"/var/www/html/sbc_realm_register_SBC_{ip}.json"
    with open(nome_arquivo, "w") as f:
        json.dump(all_data_flat, f, indent=4)

    print(f"\nJSON gerado com sucesso! Salvo em: {nome_arquivo}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Erro: IP não informado.")
        sys.exit(1)

    main(sys.argv[1])
