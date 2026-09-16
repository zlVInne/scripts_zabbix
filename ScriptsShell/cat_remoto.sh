#!/bin/bash

# Verifique se os parâmetros foram passados
if [ "$#" -ne 2 ]; then
    echo "Uso: $0 <usuário@servidor> <senha>"
    exit 1
fi

# Parâmetros
SERVER=$1
PASSWORD=$2
FILE_PATH="/tmp/system_info.json"

# Comando a ser executado no servidor remoto
sshpass -p "$PASSWORD" dbclient -y $SERVER "cat $FILE_PATH" 2>/dev/null

