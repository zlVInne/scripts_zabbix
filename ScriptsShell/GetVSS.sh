#!/bin/bash

if [ "$#" -ne 2 ]; then
    echo "Uso: $0 <usuário@servidor> <senha>"
    exit 1
fi

SERVER_FULL=$1   # Exemplo: root@172.26.40.3
PASSWORD=$2
SERVER_HOST=$(echo "$SERVER_FULL" | cut -d'@' -f2)

# Diretório de destino
DEST_DIR="/etc/zabbix/scripts"

# Cria o diretório se não existir
mkdir -p "$DEST_DIR"

# Função para baixar arquivos via dbclient + cat
baixar_arquivo() {
    local REMOTE_FILE=$1
    local LOCAL_FILE=$2

    echo "Baixando $REMOTE_FILE..."
    sshpass -p "$PASSWORD" dbclient -y "$SERVER_FULL" "cat $REMOTE_FILE" > "$LOCAL_FILE" 2>/dev/null
}

# Lista de arquivos remotos e nomes locais
baixar_arquivo "/mat/ftp/IDGRTR.RCC" "$DEST_DIR/IDGRTR_${SERVER_HOST}.RCC"
baixar_arquivo "/mat/ftp/ICHASI.RCC" "$DEST_DIR/ICHASI_${SERVER_HOST}.RCC"
baixar_arquivo "/mat/ftp/IDADRO.RCC" "$DEST_DIR/IDADRO_${SERVER_HOST}.RCC"
baixar_arquivo "/mat/ftp/ILICCE.RCC" "$DEST_DIR/ILICCE_${SERVER_HOST}.RCC"

echo "Download concluído."

