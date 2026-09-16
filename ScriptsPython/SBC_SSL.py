import paramiko
import re
import json
import time
import sys
from datetime import datetime, timezone

USERNAME = "zabbixpmi"
PASSWORD = "Zabbix2025!"


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

            if re.search(r"\n\S+>\s?$", output):
                break

        if time.time() - start_time > timeout:
            print("Timeout aguardando prompt.")
            break

        time.sleep(0.5)

    return output


def run_command(shell, command):
    shell.send(command + "\n")
    return wait_for_prompt(shell)


def parse_certificates(output):
    certs = []

    # separa blocos por certificate-record
    blocks = re.split(r"certificate-record:\s+", output)[1:]

    for block in blocks:
        lines = block.splitlines()

        cert_name = lines[0].strip()

        not_after_match = re.search(r"Not After\s*:\s*(.+)", block)

        if not_after_match:
            not_after_str = not_after_match.group(1).strip()

            try:
                expire_date = datetime.strptime(
                    not_after_str, "%b %d %H:%M:%S %Y GMT"
                ).replace(tzinfo=timezone.utc)

                expire_epoch = int(expire_date.timestamp())
                now_epoch = int(time.time())
                seconds_left = expire_epoch - now_epoch

            except Exception as e:
                print(f"Erro ao converter data: {not_after_str} - {e}")
                continue

            certs.append({
                "certificate": cert_name,
                "expire_date": not_after_str,
                "expire_epoch": expire_epoch,
                "seconds_left": seconds_left
            })

    return certs


def main(ip):
    ssh = connect_ssh(ip)
    shell = ssh.invoke_shell()
    time.sleep(3)

    if shell.recv_ready():
        shell.recv(65535)

    wait_for_prompt(shell)

    print(f"Coletando certificados do IP: {ip}...")

    output = run_command(shell, "show security certificates detail")

    certs = parse_certificates(output)

    ssh.close()

    if not certs:
        print("Nenhum certificado encontrado.")
        return

    # ALTERAÇÃO AQUI: Nome do arquivo agora inclui o IP dinamicamente
    nome_arquivo = f"sbc_certificates_{ip}.json"
    
    with open(nome_arquivo, "w") as f:
        json.dump(certs, f, indent=4)

    print(f"JSON gerado com sucesso! Salvo em: {nome_arquivo}")


if __name__ == "__main__":
    # Verifica se o IP foi passado como argumento
    if len(sys.argv) < 2:
        print("Erro: IP não informado.")
        print("Uso correto: python3 SBC_SSL.py <IP_DO_SBC>")
        sys.exit(1)

    sbc_ip = sys.argv[1]
    main(sbc_ip)
