#!/usr/bin/env bash
# Envia o código deste PC para a VM e roda o instalar.sh (instala ou atualiza).
# Vai o que está na pasta, inclusive alterações não commitadas; .env e db.sqlite3 ficam de fora.
#
# Uso, no Git Bash, na pasta do projeto: bash deploy/enviar.sh
set -euo pipefail
cd "$(dirname "$0")/.."

VM="${AIRSCAN_VM:-ubuntu@147.15.49.224}"
CHAVE="${AIRSCAN_CHAVE:-$HOME/OneDrive/Oracle/ssh-key-2026-07-07.key}"

git ls-files -z --cached --others --exclude-standard \
    | tar -c --null -T - \
    | ssh -i "$CHAVE" "$VM" \
        'rm -rf /tmp/airscan-src && mkdir /tmp/airscan-src && tar -x -C /tmp/airscan-src \
         && sudo bash /tmp/airscan-src/deploy/instalar.sh; s=$?; rm -rf /tmp/airscan-src; exit $s'
