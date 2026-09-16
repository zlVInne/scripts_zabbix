#!/bin/bash

# Verifique se os parâmetros foram passados
if [ "$#" -ne 3 ]; then
    echo "Uso: $0 <usuário@servidor> <senha>"
    exit 1
fi

# Parâmetros
SERVER=$1
PASSWORD=$2
SERVER_FILE=$3


# Comando a ser executado no servidor remoto
sshpass -p "$PASSWORD" dbclient -y $SERVER "cat /tmp/zabbix/system_info_$SERVER_FILE.json" 2>/dev/null

