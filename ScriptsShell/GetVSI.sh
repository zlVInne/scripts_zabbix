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

    # Verifica se o download teve sucesso
    if [ $? -eq 0 ] && [ -s "$LOCAL_FILE" ]; then
        echo "✅ $LOCAL_FILE baixado com sucesso"
    else
        echo "❌ Falha ao baixar $REMOTE_FILE"
    fi
}

# Lista de arquivos remotos e nomes locais
baixar_arquivo "/mat/ftp/ITRASESIP.RCC" "$DEST_DIR/ITRASESIP_${SERVER_HOST}.RCC"
baixar_arquivo "/mat/ftp/NMSITRASE.RES" "$DEST_DIR/NMSITRASE_${SERVER_HOST}.RES"
baixar_arquivo "/mat/ftp/IDADSS.rcc" "$DEST_DIR/IDADSS_${SERVER_HOST}.RCC"
baixar_arquivo "/mat/ftp/ILICCE.RCC" "$DEST_DIR/ILICCE_${SERVER_HOST}.RCC"
baixar_arquivo "/mat/ftp/NMSIDADDS.RES" "$DEST_DIR/NMSIDADDS_${SERVER_HOST}.RES"
baixar_arquivo "/mat/ftp/NMSITIGCA.RES" "$DEST_DIR/NMSITIGCA_${SERVER_HOST}.RES"
baixar_arquivo "/mat/ftp/NMSITRACA.RES" "$DEST_DIR/NMSITRACA_${SERVER_HOST}.RES"

echo "Download concluído."

