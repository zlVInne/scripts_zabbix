#!/bin/bash

# Verifique se os parâmetros foram passados
if [ "$#" -ne 3 ]; then
    echo "Uso: $0 <usuário@servidor> <senha> <ip>"
    exit 1
fi

# Parâmetros
SERVER=$1
PASSWORD=$2
IP=$3

# Executa o ping no host remoto retornando 1 se ok, 0 se falhou
RESULT=$(sshpass -p "$PASSWORD" dbclient -y "$SERVER" "ping -c1 -w1 $IP > /dev/null 2>&1 && echo 1 || echo 0" 2>/dev/null)

echo $RESULT

