#!/usr/bin/env python3
import sys
import time
import pexpect

if len(sys.argv) != 2:
    print("Uso: python3 chm_exec.py <IP>")
    sys.exit(1)

IP = sys.argv[1]
USUARIO = "sistema"
SENHA = "UgHw2R6y"
COMANDO = "idgrtr:tip=quinz,tgp=gmcv;"

# Arquivo de saída
saida = f"/etc/zabbix/scripts/IDGRTR_{IP}.RES"

child = pexpect.spawn(f"telnet {IP}", encoding="utf-8", timeout=60)

log = open(saida, "w")
child.logfile = log

# 1) Opção 2
child.expect("Opcao:")
child.sendline("2")
time.sleep(1)

# 2) Opção N
child.expect("Formato")
child.sendline("N")
time.sleep(1)

# 3) CTRL-I (abre sessão)
child.send("\x09")  # Ctrl-i
time.sleep(3)

# 4) Enviar usuário (uma única vez, sem repetir)
child.expect("USUARIO =")
child.sendline(USUARIO)
time.sleep(15)

# 5) Enviar senha
child.expect("SENHA =")
child.sendline(SENHA)
time.sleep(15)

# 6) Após prompt "<", enviar comando SEM ENTER
child.expect("<")
child.send(COMANDO)
time.sleep(20)

# 7) Fechar sessão (CTRL-K)
child.send("\x0b")  # Ctrl-k
time.sleep(2)

# 8) Fechar telnet (CTRL-Ç = CTRL-\)
child.send("\x1c")
time.sleep(1)

child.close()
log.close()

print(f"\n✅ Execução finalizada. Saída salva em: {saida}\n")

