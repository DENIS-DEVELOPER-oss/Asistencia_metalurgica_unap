#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Instala Asistencia UNAP en un VPS con Ubuntu, con dominio propio y HTTPS.
#
#   Nginx (80/443, certificado de Let's Encrypt)
#     -> Gunicorn en 127.0.0.1:PUERTO (servicio «asistencia-unap»)
#       -> MySQL/MariaDB local, con una cuenta propia de la aplicacion
#
# Pensado para un VPS COMPARTIDO con otras aplicaciones. Solo agrega cosas
# propias y no toca nada ajeno:
#   - no actualiza ni reinicia el sistema, ni instala un servidor de base
#     de datos si ya hay uno (MySQL o MariaDB);
#   - no borra ni edita sitios de Nginx de otros, solo agrega el suyo;
#   - no enciende el cortafuegos: si ya estaba activo, solo abre 80/443;
#   - elige un puerto local libre en vez de uno fijo;
#   - se detiene si 80/443 los ocupa otro servidor (Apache, Caddy, Docker).
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
# Se puede volver a ejecutar: no pisa la base, el .env ni el sitio de Nginx
# si ya existen, y sirve tambien para actualizar el codigo desde GitHub.
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
SITIO="/etc/nginx/sites-available/asistencia-unap"
SERVICIO="/etc/systemd/system/asistencia-unap.service"

alto() { echo; echo "ALTO: $*"; echo "No se cambio nada mas. Revisa el mensaje y vuelve a ejecutarlo."; exit 1; }
escucha() { ss -ltnH "sport = :$1" | grep -q .; }

[ "$(id -u)" -eq 0 ] || alto "ejecutalo como root."

echo "==> Revision previa (sin cambiar nada)"
# Puertos 80/443: tienen que estar libres o en manos de Nginx.
for p in 80 443; do
    if escucha "$p" && ! ss -ltnpH "sport = :$p" | grep -q nginx; then
        alto "el puerto $p lo usa otro programa:
$(ss -ltnpH "sport = :$p")
Esta app necesita Nginx en 80/443. Pasale este mensaje a quien te ayuda."
    fi
done
# Que ningun sitio de otra app ya use este dominio.
if [ -d /etc/nginx ] && grep -rlsE "server_name[^;]*\b${DOMINIO//./\\.}\b" /etc/nginx/sites-enabled /etc/nginx/conf.d \
        | grep -v "asistencia-unap" | grep -q .; then
    alto "otro sitio de Nginx ya usa $DOMINIO:
$(grep -rlsE "server_name[^;]*\b${DOMINIO//./\\.}\b" /etc/nginx/sites-enabled /etc/nginx/conf.d)"
fi
# Base de datos: usar la que haya; si no hay ninguna, instalar MySQL.
if systemctl list-unit-files mariadb.service 2>/dev/null | grep -q mariadb; then
    MOTOR="mariadb"
elif systemctl list-unit-files mysql.service 2>/dev/null | grep -q mysql; then
    MOTOR="mysql"
elif escucha 3306; then
    alto "el puerto 3306 lo ocupa una base de datos que no es un servicio del sistema (¿Docker?):
$(ss -ltnpH 'sport = :3306')"
else
    MOTOR=""
fi
echo "    base de datos existente: ${MOTOR:-ninguna (se instalara MySQL)}"

echo "==> Paquetes que falten (no se actualiza nada que ya este instalado)"
PAQUETES="git python3-venv python3-dev build-essential pkg-config libmysqlclient-dev nginx certbot python3-certbot-nginx"
[ -n "$MOTOR" ] || PAQUETES="$PAQUETES mysql-server"
[ "$MOTOR" = "mariadb" ] && PAQUETES="${PAQUETES/libmysqlclient-dev/libmariadb-dev-compat libmariadb-dev}"
FALTAN=""
for p in $PAQUETES; do dpkg -s "$p" >/dev/null 2>&1 || FALTAN="$FALTAN $p"; done
if [ -n "$FALTAN" ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -q
    apt-get install -y -q --no-upgrade $FALTAN
fi
[ -n "$MOTOR" ] || MOTOR="mysql"
systemctl enable --now "$MOTOR" >/dev/null 2>&1 || true

echo "==> Codigo"
id "$USUARIO" >/dev/null 2>&1 || useradd --system --home "$DIR" --shell /usr/sbin/nologin "$USUARIO"
if [ -d "$DIR/.git" ]; then
    git -C "$DIR" -c safe.directory="$DIR" pull --ff-only
else
    git clone "$REPO" "$DIR"
fi

echo "==> Entorno de Python (propio, no toca el Python de otras apps)"
[ -d "$DIR/venv" ] || python3 -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install -q --upgrade pip
"$DIR/venv/bin/pip" install -q -r "$DIR/requirements.txt" gunicorn

echo "==> Base de datos (solo la base $BASE y el usuario $USUARIO_DB)"
mysql -e "SELECT 1" >/dev/null 2>&1 || alto "no puedo entrar a $MOTOR como root sin clave.
Ejecuta:  mysql -u root -p   y avisa a quien te ayuda."
if ! mysql -e "USE $BASE" 2>/dev/null; then
    [ -f "$SQL" ] || alto "falta $SQL. Copialo desde tu PC con scp (ver cabecera)."
    mysql --default-character-set=utf8mb4 < "$SQL"
    echo "    base importada desde $SQL"
else
    echo "    la base ya existe: no se toca"
fi

echo "==> Puerto local"
PUERTO=""
if [ -f "$SERVICIO" ]; then
    PUERTO="$(grep -oE '127\.0\.0\.1:[0-9]+' "$SERVICIO" | cut -d: -f2)"
    # Se conserva solo si esta libre o si lo tiene esta misma app; si lo
    # tomo otra (MetaFlotPy usa el 8000), se busca otro.
    PID_NUESTRO="$(systemctl show -p MainPID --value asistencia-unap 2>/dev/null || echo 0)"
    if escucha "$PUERTO" && ! ss -ltnpH "sport = :$PUERTO" | grep -q "pid=$PID_NUESTRO,"; then
        PUERTO=""
    fi
fi
if [ -z "$PUERTO" ]; then
    PUERTO=8010
    while escucha "$PUERTO"; do PUERTO=$((PUERTO + 1)); done
fi
# El sitio de Nginx ya existente tiene que apuntar al mismo puerto.
[ -f "$SITIO" ] && sed -i -E "s#proxy_pass http://127\.0\.0\.1:[0-9]+;#proxy_pass http://127.0.0.1:$PUERTO;#" "$SITIO"
echo "    127.0.0.1:$PUERTO"

echo "==> Configuracion (.env)"
if [ ! -f "$DIR/.env" ]; then
    CLAVE_DB="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
    SECRETO="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
    # Solo lo necesario para trabajar con filas de SU base: nada de borrar
    # tablas ni de ver las bases de las otras apps.
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

echo "==> Estaticos"
sudo -u "$USUARIO" "$DIR/venv/bin/python" "$DIR/manage.py" collectstatic --noinput -v 0

echo "==> Servicio asistencia-unap"
cat > "$SERVICIO" <<EOF
[Unit]
Description=Asistencia UNAP (Gunicorn)
After=network.target $MOTOR.service

[Service]
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:$PUERTO --workers 3 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable asistencia-unap >/dev/null 2>&1
systemctl restart asistencia-unap

echo "==> Nginx (solo se agrega el sitio de esta app)"
if [ ! -f "$SITIO" ]; then
    cat > "$SITIO" <<EOF
server {
    listen 80;
    server_name ${HOSTS//,/ };
    client_max_body_size 5m;

    location / {
        proxy_pass http://127.0.0.1:$PUERTO;
        proxy_set_header Host \$host;
        # \$remote_addr y no \$proxy_add_x_forwarded_for: asi la IP que
        # registra el sistema es la real y nadie la puede inventar.
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
fi
ln -sf "$SITIO" /etc/nginx/sites-enabled/asistencia-unap
if ! nginx -t 2>/dev/null; then
    # Si algo falla, se retira el sitio para no dejar caido Nginx a nadie.
    rm -f /etc/nginx/sites-enabled/asistencia-unap
    nginx -t || true
    alto "la configuracion de Nginx no paso la prueba; se retiro el sitio de esta app."
fi
systemctl enable --now nginx >/dev/null 2>&1
systemctl reload nginx   # reload: las otras apps no se cortan

echo "==> Cortafuegos"
if ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow "Nginx Full" >/dev/null
    echo "    ufw activo: se abrieron 80/443"
else
    echo "    ufw inactivo: no se toca"
fi

echo "==> Certificado HTTPS (solo para $HOSTS)"
DOMINIOS=""
for h in ${HOSTS//,/ }; do DOMINIOS="$DOMINIOS -d $h"; done
certbot --nginx $DOMINIOS --redirect --agree-tos -m "$CORREO" -n --keep-until-expiring

echo
echo "Listo: https://$DOMINIO"
echo "Cambia ya las claves de admin y docentes (las del .sql son las de prueba)."
