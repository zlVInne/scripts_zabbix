#!/bin/bash

# Arquivos de origem
ARQ1="/etc/zabbix/scripts/json_metricas_rotas_172.26.40.103.json"
ARQ2="/etc/zabbix/scripts/json_metricas_rotas_172.26.40.3.json"

# Diretório de destino
DEST="/var/www/html"

# Copiar e substituir (-f força overwrite)
cp -f "$ARQ1" "$DEST/"
cp -f "$ARQ2" "$DEST/"
