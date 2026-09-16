#!/bin/bash

if [ "$#" -ne 3 ]; then
    echo "Uso: $0 <ip> <usuario> <senha>"
    exit 1
fi

IP=$1
USER=$2
PASSWORD=$3

OUTPUT_DIR="/etc/zabbix/scripts"
OUTPUT_FILE="${OUTPUT_DIR}/VPP_pm2_${IP}.json"
TMP_FILE="${OUTPUT_FILE}.tmp"
ERROR_LOG="${OUTPUT_DIR}/pm2_error_${IP}.log"

mkdir -p "$OUTPUT_DIR"

# evita duplicar user@
if [[ "$USER" == *"@"* ]]; then
    TARGET="$USER"
else
    TARGET="${USER}@${IP}"
fi

sshpass -p "$PASSWORD" dbclient -y "$TARGET" \
"export PATH=\$PATH:/usr/bin:/usr/local/bin; pm2 jlist" 2>"$ERROR_LOG" \
| /usr/bin/jq '[ .[] | {
    name: .name,
    status: .pm2_env.status,
    cpu: .monit.cpu,
    mem: .monit.memory,
    restart: .pm2_env.restart_time,
    uptime: .pm2_env.pm_uptime
} ]' > "$TMP_FILE"

if [ -s "$TMP_FILE" ]; then
    mv "$TMP_FILE" "$OUTPUT_FILE"
    echo "OK: file created ${OUTPUT_FILE}"
    exit 0
else
    rm -f "$TMP_FILE"
    echo "ERROR: file not created"
    echo "Check ${ERROR_LOG}"
    exit 2
fi

