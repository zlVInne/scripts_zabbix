#!/bin/bash

# 1. Verifica se os 3 parâmetros foram passados
if [ "$#" -ne 3 ]; then
    echo '{"status":"ERRO", "msg":"Uso incorreto. Requer <usuário@servidor> <senha> <prefixo_da_central>"}'
    exit 1
fi

SERVER=$1
PASSWORD=$2
CENTRAL=$3

# Extrai apenas o IP ou Hostname (remove o "usuario@" caso tenha sido passado)
IP=$(echo "$SERVER" | awk -F@ '{print $NF}')

# Define o caminho do arquivo de saída
DEST_DIR="/etc/zabbix/scripts"
DEST_FILE="${DEST_DIR}/backup_${IP}.json"

# Verifica/Cria o diretório se não existir (necessário rodar com permissão suficiente)
if [ ! -d "$DEST_DIR" ]; then
    mkdir -p "$DEST_DIR" 2>/dev/null
fi

# 2. Monta o comando (bloco que roda remoto)
REMOTE_CMD="PREFIXO=\"$CENTRAL\"; $(cat << 'EOF'
DIR="/mat/bkp"

# Padrão de busca:
# - ${PREFIXO}* permite buscar por nome parcial (ex: "VSI" encontra "VSIJDO")
# - *.t* pega extensões como .tgz, .tar.xz, .tar.gz e descarta .md5
PATTERN="${PREFIXO}*.t*"

# 1. Pega o arquivo mais recente
LATEST_FILE=$(ls -t $DIR/$PATTERN 2>/dev/null | head -1)

if [ -z "$LATEST_FILE" ]; then
    echo "{\"status\": \"NOK\", \"msg\": \"Nenhum arquivo de backup encontrado para o prefixo ${PREFIXO}.\"}"
    exit 0
fi

# 2. Obtém o timestamp do arquivo
MTIME=$(date -r "$LATEST_FILE" +%s 2>/dev/null)
[ -z "$MTIME" ] && MTIME=$(stat -f %m "$LATEST_FILE" 2>/dev/null)
[ -z "$MTIME" ] && MTIME=$(stat -c %Y "$LATEST_FILE" 2>/dev/null)

CURRENT_TIME=$(date +%s)
AGE_SECONDS=$((CURRENT_TIME - MTIME))

# 3. Coleta os indicadores de quantidade
TOTAL_FILES=$(find "$DIR" -maxdepth 1 -name "$PATTERN" -type f 2>/dev/null | wc -l)
FILES_LAST_7D=$(find "$DIR" -maxdepth 1 -name "$PATTERN" -mtime -7 -type f 2>/dev/null | wc -l)
FILES_OLDER_7D=$(find "$DIR" -maxdepth 1 -name "$PATTERN" -mtime +7 -type f 2>/dev/null | wc -l)

# 4. Obtém o tamanho do último arquivo em bytes
SIZE_BYTES=$(ls -l "$LATEST_FILE" | awk '{print $5}')

# --- NOVOS INDICADORES (Crescimento e Histórico) ---

# 4.1. Tamanho do penúltimo backup (para calcular o crescimento)
SECOND_LATEST=$(cd "$DIR" && ls -t $PATTERN 2>/dev/null | sed -n '2p')
if [ -n "$SECOND_LATEST" ]; then
    PREV_SIZE_BYTES=$(cd "$DIR" && ls -l "$SECOND_LATEST" | awk '{print $5}')
else
    # Se só existe 1 arquivo, assumimos que não houve crescimento
    PREV_SIZE_BYTES=$SIZE_BYTES
fi
GROWTH_BYTES=$((SIZE_BYTES - PREV_SIZE_BYTES))

# 4.2. Cria lista detalhada (array JSON) de arquivos e tamanhos
FILE_LIST_JSON=$(cd "$DIR" && ls -lt $PATTERN 2>/dev/null | grep -v '^total' | awk '{
    if (count > 0) printf ",\n"
    printf "    {\"file\": \"%s\", \"size_bytes\": %s}", $NF, $5
    count++
}')

# ---------------------------------------------------

# 5. Lógica de Status
STATUS="OK"
MSG="Backup Saudavel"

if [ "$AGE_SECONDS" -gt 86400 ]; then
    STATUS="NOK"
    MSG="Backup atrasado: ultimo arquivo tem mais de 24h."
elif [ "$FILES_LAST_7D" -lt 7 ]; then
    STATUS="NOK"
    MSG="Menos de 7 backups gerados nos ultimos 7 dias."
elif [ "$SIZE_BYTES" -lt 10000000 ]; then
    STATUS="NOK"
    MSG="Ultimo backup gerado e muito pequeno (possivelmente corrompido)."
fi

# 6. Imprime a saída formatada em JSON
cat <<JSON
{
  "status": "$STATUS",
  "msg": "$MSG",
  "latest_file": "$(basename "$LATEST_FILE")",
  "age_seconds": $AGE_SECONDS,
  "size_bytes": $SIZE_BYTES,
  "prev_size_bytes": $PREV_SIZE_BYTES,
  "growth_bytes": $GROWTH_BYTES,
  "total_files": $TOTAL_FILES,
  "files_last_7d": $FILES_LAST_7D,
  "files_older_7d": $FILES_OLDER_7D,
  "files_details": [
$FILE_LIST_JSON
  ]
}
JSON
EOF
)"

# 3. Executa remotamente e salva o resultado no arquivo
sshpass -p "$PASSWORD" dbclient -y $SERVER "$REMOTE_CMD" > "$DEST_FILE" 2>/dev/null

# 4. Valida se o arquivo foi criado com sucesso e exibe na tela para o Zabbix ler
if [ -s "$DEST_FILE" ]; then
    cat "$DEST_FILE"
else
    echo '{"status":"ERRO", "msg":"Falha ao gerar ou salvar o arquivo em '"$DEST_FILE"'"}'
    exit 1
fi
