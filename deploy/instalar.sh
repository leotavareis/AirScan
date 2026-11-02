#!/usr/bin/env bash
# Instala ou atualiza o AirScan na VM, isolado do resto do sistema.
# Só cria coisas novas: usuário airscan, /var/www/airscan, units airscan*, site nginx "airscan"
# e o certificado de airscan.tzurapp.com.br. Pode rodar de novo quantas vezes quiser.
#
# Uso, na VM, a partir de uma cópia do código: sudo bash deploy/instalar.sh
# (o deploy/enviar.sh faz isso a partir do PC). Para remover: deploy/desinstalar.sh
set -euo pipefail

DOMINIO=airscan.tzurapp.com.br
USUARIO=airscan
APP=/home/$USUARIO/AirScan
WWW=/var/www/airscan
SITE=/etc/nginx/sites-available/airscan
CERT=/etc/letsencrypt/live/$DOMINIO/fullchain.pem
ORIGEM="$(cd "$(dirname "$0")/.." && pwd)"
UV=/home/$USUARIO/.local/bin/uv
IP_VM=147.15.49.224

[ "$(id -u)" = 0 ] || { echo "Rode com sudo."; exit 1; }

passo() { echo; echo "==> $*"; }
como_app() { sudo -u "$USUARIO" -H bash -c "cd '$APP' && $*"; }

passo "Usuário $USUARIO"
id "$USUARIO" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$USUARIO"

passo "Código em $APP (mantém .env, banco e .venv)"
install -d -o "$USUARIO" -g "$USUARIO" "$APP"
if [ "$ORIGEM" != "$APP" ]; then
    tar -C "$ORIGEM" -c --exclude=./.env --exclude=./db.sqlite3 --exclude=./.venv . \
        | sudo -u "$USUARIO" tar -x --no-same-owner -C "$APP"
fi

passo "Python 3.14 e dependências (uv, só para o usuário $USUARIO)"
if [ ! -x "$UV" ]; then
    sudo -u "$USUARIO" -H bash -c 'curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh'
fi
como_app "[ -d .venv ] || '$UV' venv --python 3.14 .venv"
como_app "'$UV' pip install --quiet --python .venv/bin/python -r requirements.txt"

if [ ! -f "$APP/.env" ]; then
    passo "Criando .env de produção"
    CHAVE="$(como_app ".venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(50))'")"
    sed -e 's/\r$//' \
        -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$CHAVE|" \
        -e "s|^DJANGO_DEBUG=.*|DJANGO_DEBUG=0|" \
        -e "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$DOMINIO|" \
        -e "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMINIO|" \
        "$APP/.env.example" > "$APP/.env"
    echo "DJANGO_STATIC_ROOT=$WWW/static" >> "$APP/.env"
    chown "$USUARIO:$USUARIO" "$APP/.env"
    chmod 600 "$APP/.env"
    echo "Preencha TELEGRAM_* e SERPAPI_API_KEY em $APP/.env"
fi

passo "Banco e arquivos estáticos"
install -d "$WWW" "$WWW/acme"
install -d -o "$USUARIO" -g "$USUARIO" "$WWW/static"
como_app ".venv/bin/python manage.py migrate --noinput"
como_app ".venv/bin/python manage.py collectstatic --noinput --clear -v 0"

passo "Serviços systemd"
install -m 644 "$APP"/deploy/systemd/airscan.service "$APP"/deploy/systemd/airscan-checar.* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --quiet airscan.service airscan-checar.timer
systemctl restart airscan.service
systemctl start airscan-checar.timer

# Troca o site do nginx só se "nginx -t" aprovar; senão volta como estava e para.
aplicar_nginx() {
    local backup=""
    [ -f "$SITE" ] && backup="$(mktemp)" && cp "$SITE" "$backup"
    cat > "$SITE"
    ln -sfn "$SITE" /etc/nginx/sites-enabled/airscan
    if nginx -t 2>/dev/null; then
        systemctl reload nginx
    else
        nginx -t || true
        if [ -n "$backup" ]; then cp "$backup" "$SITE"; else rm -f "$SITE" /etc/nginx/sites-enabled/airscan; fi
        echo "Config do nginx recusada; nada foi recarregado."
        exit 1
    fi
}

passo "Nginx (sites-available/airscan)"
if [ -f "$CERT" ]; then
    aplicar_nginx < "$APP/deploy/nginx/airscan.conf"
else
    sed '/^# --- HTTPS ---/,$d' "$APP/deploy/nginx/airscan.conf" | aplicar_nginx

    passo "Certificado HTTPS para $DOMINIO"
    IP_DNS="$(getent ahostsv4 "$DOMINIO" | awk 'NR==1 {print $1}' || true)"
    if [ -z "$IP_DNS" ] || [ "$IP_DNS" != "$IP_VM" ]; then
        echo "O DNS de $DOMINIO ainda não aponta para esta VM (${IP_DNS:-sem resposta} != ${IP_VM:-?})."
        echo "Rode este script de novo quando apontar; o site fica só em HTTP até lá."
        exit 0
    fi
    certbot certonly --webroot -w "$WWW/acme" -d "$DOMINIO" \
        --non-interactive --agree-tos --register-unsafely-without-email \
        --deploy-hook "systemctl reload nginx"
    aplicar_nginx < "$APP/deploy/nginx/airscan.conf"
fi

passo "Pronto: https://$DOMINIO"
systemctl --no-pager --lines=0 status airscan.service | head -3 || true
systemctl list-timers --no-pager airscan-checar.timer | head -2 || true
