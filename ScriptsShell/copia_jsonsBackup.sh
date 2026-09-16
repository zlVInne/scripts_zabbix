#!/bin/bash

SRC_DIR="/etc/zabbix/scripts"
DEST_DIR="/var/www/html"

# Verifica se o diretório de destino existe; se não, cria
if [ ! -d "$DEST_DIR" ]; then
    mkdir -p "$DEST_DIR"
fi

# Copia todos os arquivos que começam com "backup_" e terminam com ".json".
# O 2>/dev/null oculta mensagens de erro caso não haja arquivos no momento.
cp "$SRC_DIR"/backup_*.json "$DEST_DIR"/ 2>/dev/null

# Opcional: Garante que os arquivos copiados tenham permissão de leitura para o servidor web
chmod 644 "$DEST_DIR"/backup_*.json 2>/dev/null

exit 0
