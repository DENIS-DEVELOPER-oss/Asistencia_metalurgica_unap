#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Instala Asistencia UNAP en un VPS con Ubuntu, con dominio propio y HTTPS.
#
#   Nginx (80/443, certificado de Let's Encrypt)
#     -> Gunicorn en 127.0.0.1:8000 (servicio «asistencia-unap»)
#       -> MySQL local, con una cuenta propia de la aplicacion
#
# Antes de ejecutarlo:
#   1. El dominio (registro A) tiene que apuntar ya a la IP de este VPS.
#   2. Copia la base desde tu PC (no esta en GitHub porque trae los datos
#      reales de los alumnos):
#        scp base_de_datos/asistencia_unap_instalar.sql root@IP_DEL_VPS:/root/
#
# Uso (como root):
#   bash instalar_vps.sh midominio.com correo@ejemplo.com
#
# Se puede volver a ejecutar: no pisa la base ni el .env si ya existen, y
# sirve tambien para actualizar el codigo desde GitHub.
# ---------------------------------------------------------------------------
set -euo pipefail

DOMINIO="${1:?Uso: bash instalar_vps.sh midominio.com correo@ejemplo.com}"
CORREO="${2:?Falta el correo (Lets Encrypt avisa ahi si el certificado va a caducar)}"

REPO="https://github.com/DENIS-DEVELOPER-oss/Asistencia_metalurgica_unap.git"
DIR="/srv/asistencia-unap"
USUARIO="asistencia"
SQL="/root/asistencia_unap_instalar.sql"
BASE="asistencia_unap"
USUARIO_DB="asistencia_app"

[ "$(id -u)" -eq 0 ] || { echo "Ejecutalo como root."; exit 1; }

echo "==> Paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q git python3-venv python3-dev build-essential pkg-config \
    default-libmysqlclient-dev mysql-server nginx certbot python3-certbot-nginx ufw

echo "==> Codigo"
id "$USUARIO" >/dev/null 2>&1 || useradd --system --home "$DIR" --shell /usr/sbin/nologin "$USUARIO"
if [ -d "$DIR/.git" ]; then
    git -C "$DIR" pull --ff-only
else
    git clone "$REPO" "$DIR"
fi
git config --global --add safe.directory "$DIR"

echo "==> Entorno de Python"
[ -d "$DIR/venv" ] || python3 -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install -q --upgrade pip
"$DIR/venv/bin/pip" install -q -r "$DIR/requirements.txt" gunicorn

echo "==> Base de datos"
systemctl enable --now mysql
if ! mysql -e "USE $BASE" 2>/dev/null; then
    [ -f "$SQL" ] || { echo "Falta $SQL. Copialo desde tu PC con scp (ver cabecera)."; exit 1; }
    mysql --default-character-set=utf8mb4 < "$SQL"
    echo "    base importada desde $SQL"
fi

echo "==> Configuracion (.env)"
if [ ! -f "$DIR/.env" ]; then
    CLAVE_DB="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
    SECRETO="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
    # Solo lo necesario para trabajar con filas: nada de borrar tablas.
    mysql -e "CREATE USER IF NOT EXISTS '$USUARIO_DB'@'localhost' IDENTIFIED BY '$CLAVE_DB';
              ALTER USER '$USUARIO_DB'@'localhost' IDENTIFIED BY '$CLAVE_DB';
              GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE, SHOW VIEW, LOCK TABLES ON \`$BASE\`.* TO '$USUARIO_DB'@'localhost';
              FLUSH PRIVILEGES;"
    HOSTS="$DOMINIO"
    getent hosts "www.$DOMINIO" >/dev/null && HOSTS="$DOMINIO,www.$DOMINIO"
    cat > "$DIR/.env" <<EOF
SECRET_KEY=$SECRETO
DEBUG=False
USAR_HTTPS=True
DETRAS_DE_PROXY=True
MINUTOS_DE_INACTIVIDAD=180
ALLOWED_HOSTS=$HOSTS
DB_NAME=$BASE
DB_USER=$USUARIO_DB
DB_PASSWORD=$CLAVE_DB
DB_HOST=localhost
DB_PORT=3306
UMBRAL_INHABILITACION=30
EOF
    echo "    .env creado"
fi
HOSTS="$(grep '^ALLOWED_HOSTS=' "$DIR/.env" | cut -d= -f2)"

chown -R "$USUARIO:$USUARIO" "$DIR"
chmod 600 "$DIR/.env"

echo "==> Estaticos y revision de Django"
sudo -u "$USUARIO" "$DIR/venv/bin/python" "$DIR/manage.py" collectstatic --noinput -v 0
sudo -u "$USUARIO" "$DIR/venv/bin/python" "$DIR/manage.py" check --deploy || true

echo "==> Servicio"
cat > /etc/systemd/system/asistencia-unap.service <<EOF
[Unit]
Description=Asistencia UNAP (Gunicorn)
After=network.target mysql.service

[Service]
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable asistencia-unap
systemctl restart asistencia-unap

echo "==> Nginx"
# Solo la primera vez: despues certbot le agrega el bloque HTTPS.
if [ ! -f /etc/nginx/sites-available/asistencia-unap ]; then
cat > /etc/nginx/sites-available/asistencia-unap <<EOF
server {
    listen 80;
    server_name ${HOSTS//,/ };
    client_max_body_size 5m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        # \$remote_addr y no \$proxy_add_x_forwarded_for: asi la IP que
        # registra el sistema es la real y nadie la puede inventar.
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
fi
ln -sf /etc/nginx/sites-available/asistencia-unap /etc/nginx/sites-enabled/asistencia-unap
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> Cortafuegos"
ufw allow OpenSSH >/dev/null
ufw allow "Nginx Full" >/dev/null
ufw --force enable >/dev/null

echo "==> Certificado HTTPS"
DOMINIOS=""
for h in ${HOSTS//,/ }; do DOMINIOS="$DOMINIOS -d $h"; done
certbot --nginx $DOMINIOS --redirect --agree-tos -m "$CORREO" -n

echo
echo "Listo: https://$DOMINIO"
echo "Cambia ya las claves de admin y docentes (las del .sql son las de prueba)."
