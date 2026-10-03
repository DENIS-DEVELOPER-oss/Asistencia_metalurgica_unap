"""
Configuración de Django para el Sistema de Control de Asistencia - UNAP.

Proyecto único: las pantallas se renderizan con plantillas de Django, sin
frontend aparte ni Node.

IMPORTANTE: la base de datos `asistencia_unap` es la fuente de verdad.
Todos los modelos son `managed = False`; NO se ejecutan migraciones que
alteren su estructura.
"""
import os
import warnings
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(clave, por_defecto=""):
    return os.getenv(clave, por_defecto)


def env_bool(clave, por_defecto=False):
    valor = os.getenv(clave)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def env_list(clave, por_defecto=""):
    return [item.strip() for item in os.getenv(clave, por_defecto).split(",") if item.strip()]


# ---------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------
# Claves que trae el proyecto de fábrica: sirven para arrancar en una PC
# nueva, nunca para operar de verdad.
CLAVES_DE_FABRICA = {
    "",
    "django-inseguro-clave-de-desarrollo",
    "django-inseguro-cambia-esta-clave-en-produccion",
}

SECRET_KEY = env("SECRET_KEY", "django-inseguro-clave-de-desarrollo")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

# Las sesiones viajan firmadas dentro de la cookie del navegador, así que la
# SECRET_KEY es lo único que impide falsificar una sesión de administrador.
# Con DEBUG=False se corta el arranque; en desarrollo basta con avisar.
if SECRET_KEY in CLAVES_DE_FABRICA:
    aviso = (
        "SECRET_KEY sigue siendo la clave de ejemplo. Copia .env.example a .env "
        "y escribe una clave propia; puedes generarla con:  "
        'python -c "import secrets; print(secrets.token_urlsafe(50))"'
    )
    if DEBUG:
        warnings.warn(aviso, RuntimeWarning, stacklevel=2)
    else:
        raise ImproperlyConfigured(aviso)

# ---------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "cuentas",
    "academico",
    "asistencia",
    "reportes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sirve los archivos estaticos desde el propio proceso. Sin esto, con
    # DEBUG=False la aplicacion se ve sin estilos ni escudo, porque
    # Django deja de servirlos y no hay un servidor web delante.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Cabeceras que hay que armar en cada peticion: la politica de
    # contenido con su nonce, los permisos del navegador y el
    # no-guardar-en-cache de las pantallas con datos de alumnos.
    "config.middleware.CabecerasDeSeguridad",
    # Una clave que puso el administrador vale para entrar una vez: hasta
    # que su dueño elija la suya, esto no deja pasar de «Mi cuenta».
    "config.middleware.ClavePendienteDeCambio",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cuentas.context_processors.grupos_del_usuario",
                "config.middleware.nonce_para_plantillas",
            ],
        },
    },
]

# ---------------------------------------------------------------------
# Sesiones: se guardan firmadas en la cookie del navegador.
# Así NO hace falta la tabla `django_session` y la base de datos de la
# universidad queda intacta.
# ---------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

# Cuanto puede quedarse quieta una sesion antes de caducar. Con
# SESSION_SAVE_EVERY_REQUEST la cuenta se reinicia en cada pantalla que se
# abre, asi que son minutos SIN USAR el sistema, no de duracion total: una
# clase entera no se corta. Importa porque la PC del aula es compartida y
# un docente que se levanta sin cerrar sesion deja su cuenta abierta.
MINUTOS_DE_INACTIVIDAD = int(env("MINUTOS_DE_INACTIVIDAD", "180"))
SESSION_COOKIE_AGE = MINUTOS_DE_INACTIVIDAD * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

# ---------------------------------------------------------------------
# Base de datos (MySQL 8 / MariaDB 10.5+) — estructura preexistente
# ---------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME", "asistencia_unap"),
        "USER": env("DB_USER", "root"),
        "PASSWORD": env("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "CONN_MAX_AGE": 60,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# El esquema lo define asistencia_unap.sql: desactivamos las migraciones de
# las apps de Django para que `migrate` no cree tablas auxiliares.
MIGRATION_MODULES = {"auth": None, "contenttypes": None, "sessions": None}

# ---------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------
AUTH_USER_MODEL = "cuentas.Usuario"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "cursos"
LOGOUT_REDIRECT_URL = "login"

# Sin `NumericPasswordValidator`: la universidad usa el DNI como clave
# inicial del docente, y ese validador rechaza cualquier clave que sea
# solo digitos. Se mantienen el largo minimo y la lista de claves
# comunes, que son los que atajan lo peor.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# ---------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------
LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
# En Perú el separador decimal es el punto (ver config/formats/).
FORMAT_MODULE_PATH = ["config.formats"]
# `fecha` y `hora_inicio` son la hora local del aula: sin conversión a UTC.
USE_TZ = False

# ---------------------------------------------------------------------
# Archivos estáticos
# ---------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise comprime y pone un hash en el nombre de cada archivo, de modo
# que el navegador puede cachearlos para siempre y aun asi recibir la
# version nueva en cuanto cambian.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------------------------------------------------------------------
# Reglas de negocio
# ---------------------------------------------------------------------
# Un alumno queda en riesgo de inhabilitación si su porcentaje de faltas
# supera este umbral.
UMBRAL_INHABILITACION = float(env("UMBRAL_INHABILITACION", "30"))

# Semáforo de asistencia usado en pantalla y en los reportes.
SEMAFORO_VERDE = 85.0
SEMAFORO_AMBAR = 70.0

# ---------------------------------------------------------------------
# Seguridad del transporte
# ---------------------------------------------------------------------
# En la red de la universidad el sistema se sirve por HTTP, y marcar las
# cookies como «solo por HTTPS» impediria iniciar sesion. Por eso van
# apagadas por defecto y se encienden desde el .env el dia que el sistema
# este detras de HTTPS, sin tocar el codigo.
USAR_HTTPS = env_bool("USAR_HTTPS", False)

SESSION_COOKIE_SECURE = USAR_HTTPS
CSRF_COOKIE_SECURE = USAR_HTTPS
SECURE_SSL_REDIRECT = USAR_HTTPS
SECURE_HSTS_SECONDS = 31536000 if USAR_HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = USAR_HTTPS
SECURE_HSTS_PRELOAD = USAR_HTTPS

# Si algun dia el sistema queda detras de un proxy (nginx, IIS) que
# termina el HTTPS, hay que decirlo: solo entonces se hace caso a las
# cabeceras que el proxy anade, y con ellas la IP real del visitante y el
# aviso de que la conexion ya viene cifrada. Sin proxy delante, esas
# cabeceras las puede escribir cualquiera, asi que se ignoran.
DETRAS_DE_PROXY = env_bool("DETRAS_DE_PROXY", False)
if DETRAS_DE_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Estas no dependen de HTTPS y valen siempre.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Topes de lo que se acepta en un formulario. El llamado de asistencia
# envia dos campos por alumno, asi que 2000 deja sitio a una lista de mil
# estudiantes y al mismo tiempo corta un envio inflado a proposito para
# hacer trabajar al servidor.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# Las IP desde las que se entra tienen que constar como origen de
# confianza para que el formulario pase el control CSRF.
CSRF_TRUSTED_ORIGINS = [
    f"{'https' if USAR_HTTPS else 'http'}://{host}"
    for host in ALLOWED_HOSTS
    if host not in ("*",)
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detallado": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "detallado"},
        # Con DEBUG=False los errores ya no salen en pantalla: si no se
        # guardan en algun sitio, se pierden.
        "archivo": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "asistencia.log",
            "maxBytes": 2 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
            "formatter": "detallado",
        },
    },
    "loggers": {
        # Django registra cada 403 y cada 404 con su traza completa. Aquí
        # no son errores sino el sistema funcionando: un docente que abre
        # /administracion/ recibe un 403 porque asi esta previsto. Dejarlo
        # en WARNING llena el registro de trazas y entierra lo que si
        # importa, que son los 500. Se sube a ERROR, de modo que los
        # rechazos no se anotan y los fallos de verdad si.
        "django.request": {
            "handlers": ["console", "archivo"],
            "level": "ERROR",
            "propagate": False,
        },
        # El servidor anuncia cada peticion servida; con una clase de 30
        # alumnos eso son cientos de lineas por sesion.
        "waitress": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
    "root": {"handlers": ["console", "archivo"], "level": "INFO"},
}
