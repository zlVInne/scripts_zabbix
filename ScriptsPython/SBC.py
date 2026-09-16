import paramiko
import re
import json
import time
import sys

USERNAME = "zabbixpmi"
PASSWORD = "Zabbix2025!"

REALMS = ["Access-CGE", "Access-Ciops", "Access-FECOMERCIO"]


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

            # Detecta prompt dinamicamente (termina com >)
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


def extract_users(brief_output):
    return list(set(re.findall(r"sip:(\d+)@[\w\.]+", brief_output)))


def extract_details(detailed_output, realm):
    data = {}

    name = re.search(r"Name:\s+(sip:[^\s]+)", detailed_output)
    valid = re.search(r"Valid:\s+(\w+)", detailed_output)
    registered = re.search(r"Registered at:\s+([\d\-:]+)", detailed_output)
    last_registered = re.search(r"Last Registered at:\s+([\d\-:]+)", detailed_output)
    registrar_ip = re.search(r"Registrar IP:\s+([\d\.]+)", detailed_output)

    if name:
        data["Name"] = name.group(1)
    if valid:
        data["Valid"] = valid.group(1)
    if registered:
        data["Registered at"] = registered.group(1)
    if last_registered:
        data["Last Registered at"] = last_registered.group(1)
    if registrar_ip:
        data["Registrar IP"] = registrar_ip.group(1)

    data["Realm"] = realm

    return data


def main(ip):
    ssh = connect_ssh(ip)
    shell = ssh.invoke_shell()
    time.sleep(3)

    # Limpa buffer inicial
    if shell.recv_ready():
        shell.recv(65535)

    wait_for_prompt(shell)

    all_users_data = []
    processed_users = set()

    print(f"Coletando registros do IP: {ip}...")

    for realm in REALMS:
        print(f"\nConsultando realm: {realm}")

        output = run_command(shell, f"show registration sipd by-realm {realm} brief")
        users = extract_users(output)

        print(f"{len(users)} usuários encontrados no realm {realm}")

        for user in users:
            if user in processed_users:
                continue

            detailed = run_command(shell, f"show registration sipd by-user {user} detailed")
            user_data = extract_details(detailed, realm)

            if user_data:
                all_users_data.append(user_data)
                processed_users.add(user)

    ssh.close()

    if not all_users_data:
        print("Nenhum usuário registrado encontrado.")
        return

    # Nome do arquivo gerado dinamicamente com o IP
    nome_arquivo = f"sbc_registrations_{ip}.json"

    with open(nome_arquivo, "w") as f:
        json.dump(all_users_data, f, indent=4)

    print(f"\nJSON gerado com sucesso! Salvo em: {nome_arquivo}")


if __name__ == "__main__":
    # Verifica se o IP foi passado como argumento
    if len(sys.argv) < 2:
        print("Erro: IP não informado.")
        print("Uso correto: python3 sbc_registrations.py <IP_DO_SBC>")
        sys.exit(1)

    sbc_ip = sys.argv[1]
    main(sbc_ip)
