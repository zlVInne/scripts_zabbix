#!/bin/bash

if [ "$#" -ne 2 ]; then
    echo "Uso: $0 <usuário@servidor> <senha>"
    exit 1
fi

sshpass -p "$2" scp \
    -oKexAlgorithms=+diffie-hellman-group1-sha1 \
    -oHostKeyAlgorithms=+ssh-rsa \
    "$1:/mat/ftp/IDGRTR.RCC" /tmp/IDGRTR.RCC

sshpass -p "$2" scp \
    -oKexAlgorithms=+diffie-hellman-group1-sha1 \
    -oHostKeyAlgorithms=+ssh-rsa \
    "$1:/mat/ftp/ICHASI.RCC" /tmp/ICHASI.RCC

echo "Download concluído."
