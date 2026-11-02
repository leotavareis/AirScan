#!/usr/bin/env bash
# Remove tudo o que o instalar.sh criou na VM, sem tocar no resto do sistema.
# Apaga também o banco (rotas e histórico) e o .env.
#
# Uso, na VM: sudo bash /home/airscan/AirScan/deploy/desinstalar.sh
set -euo pipefail

DOMINIO=airscan.tzurapp.com.br
USUARIO=airscan

[ "$(id -u)" = 0 ] || { echo "Rode com sudo."; exit 1; }

if [ "${1:-}" != "--sim" ]; then
    read -r -p "Remover o AirScan, o banco e o certificado de $DOMINIO? Digite 'sim': " resposta
    [ "$resposta" = "sim" ] || { echo "Cancelado."; exit 1; }
fi

# Copia este script antes de apagar a pasta onde ele está.
if [ "${AIRSCAN_DESINSTALANDO:-}" != 1 ]; then
    copia="$(mktemp)"; cp "$0" "$copia"
    AIRSCAN_DESINSTALANDO=1 exec bash "$copia" --sim
fi

systemctl disable --now airscan.service airscan-checar.timer 2>/dev/null || true
rm -f /etc/systemd/system/airscan.service /etc/systemd/system/airscan-checar.service /etc/systemd/system/airscan-checar.timer
systemctl daemon-reload

rm -f /etc/nginx/sites-enabled/airscan /etc/nginx/sites-available/airscan
nginx -t && systemctl reload nginx

certbot delete --cert-name "$DOMINIO" --non-interactive 2>/dev/null || true

if id "$USUARIO" >/dev/null 2>&1; then
    pkill -u "$USUARIO" 2>/dev/null || true
    userdel -r "$USUARIO" 2>/dev/null || true
fi
rm -rf /var/www/airscan

echo "AirScan removido. Se quiser, apague o registro A 'airscan' no Registro.br."
