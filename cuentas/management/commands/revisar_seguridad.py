"""
Revisión de seguridad del sistema, en una sola pasada.

Junta en una pantalla lo que de otro modo hay que ir a buscar a tres
sitios: la configuración del .env, el estado de las cuentas y lo que dice
el registro de los últimos días. Está pensado para ejecutarlo antes de
abrir el sistema al ciclo y, de ahí en adelante, cada cierto tiempo.

Uso:
    python manage.py revisar_seguridad
    python manage.py revisar_seguridad --dias 30
    python manage.py revisar_seguridad --podar     (borra lo caducado)
"""
import datetime
import pathlib
import sys
from datetime import timedelta

import django
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Count
from django.utils import timezone

from cuentas.models import Docente, Usuario
from cuentas.seguridad import (
    DIAS_QUE_SE_GUARDA,
    LIMITE_POR_IP,
    LIMITE_POR_USUARIO,
    VENTANA,
    Evento,
    EventoSeguridad,
    limpiar_antiguos,
)

CLAVE_SIN_DEFINIR = "PENDIENTE_DEFINIR"


class Command(BaseCommand):
    help = "Revisa la configuración de seguridad y el registro de accesos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int, default=7,
            help="Cuántos días del registro se resumen (por defecto 7).",
        )
        parser.add_argument(
            "--podar", action="store_true",
            help=f"Borra las anotaciones de más de {DIAS_QUE_SE_GUARDA} días.",
        )

    # -- Presentación --------------------------------------------------
    def titulo(self, texto):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(texto))

    def bien(self, texto):
        self.stdout.write(self.style.SUCCESS(f"  [ok]    {texto}"))

    def ojo(self, texto):
        self.avisos += 1
        self.stdout.write(self.style.WARNING(f"  [ojo]   {texto}"))

    def mal(self, texto):
        self.problemas += 1
        self.stdout.write(self.style.ERROR(f"  [FALLA] {texto}"))

    def dato(self, texto):
        self.stdout.write(f"          {texto}")

    # -- Revisión ------------------------------------------------------
    def handle(self, *args, **opciones):
        self.avisos = 0
        self.problemas = 0

        self.revisar_configuracion()
        self.revisar_base_de_datos()
        self.revisar_cuentas()
        self.revisar_respaldos()
        self.revisar_registro(opciones["dias"])

        if opciones["podar"]:
            self.titulo("MANTENIMIENTO")
            borrados = limpiar_antiguos()
            self.dato(f"{borrados} anotación(es) de más de {DIAS_QUE_SE_GUARDA} días borradas.")

        self.resumen()

    def revisar_configuracion(self):
        self.titulo("CONFIGURACIÓN")

        if settings.DEBUG:
            self.mal(
                "DEBUG=True. Cualquier error muestra en pantalla la "
                "configuración entera, contraseña de MySQL incluida. "
                "Ponlo en False en el archivo .env."
            )
        else:
            self.bien("DEBUG=False: los errores no se muestran al visitante.")

        if settings.SECRET_KEY in settings.CLAVES_DE_FABRICA:
            self.mal("SECRET_KEY es la de ejemplo: se pueden falsificar sesiones.")
        else:
            self.bien("SECRET_KEY propia.")

        if "*" in settings.ALLOWED_HOSTS:
            self.ojo("ALLOWED_HOSTS acepta cualquier nombre de servidor.")
        else:
            self.bien(f"ALLOWED_HOSTS: {', '.join(settings.ALLOWED_HOSTS)}")

        if settings.USAR_HTTPS:
            self.bien("HTTPS activo: cookies seguras y HSTS encendidos.")
        else:
            self.ojo(
                "El sistema va por HTTP. En la red del aula la contraseña "
                "viaja sin cifrar; enciéndelo con USAR_HTTPS=True el día "
                "que haya un certificado delante."
            )

        self.dato(f"Django {django.get_version()} · Python "
                  f"{sys.version.split()[0]}")

        minutos = settings.SESSION_COOKIE_AGE // 60
        self.bien(f"La sesión caduca tras {minutos} minutos sin usarse.")
        self.bien(
            f"Acceso: {LIMITE_POR_USUARIO} intentos por cuenta y "
            f"{LIMITE_POR_IP} por equipo cada {int(VENTANA.total_seconds() // 60)} minutos."
        )

    def revisar_base_de_datos(self):
        """
        Con qué cuenta entra la aplicación a MySQL, y qué puede hacer con ella.

        Es el punto ciego típico: todo el control de acceso del sistema se
        aplica dentro de la aplicación, y quien se conecta por debajo a la
        base se lo salta entero. Los disparadores que impiden tocar una
        clase cerrada protegen a la aplicación, no a la base.
        """
        self.titulo("BASE DE DATOS")

        base = settings.DATABASES["default"]
        usuario, clave = base["USER"], base["PASSWORD"]

        if usuario == "root":
            self.mal(
                "La aplicación entra a MySQL como root: cualquier fallo suyo "
                "tendría permiso para borrar la base entera. Créale una "
                "cuenta propia con:  manage.py crear_usuario_mysql"
            )
        elif not clave:
            self.mal(
                f"La cuenta «{usuario}» no tiene contraseña. Vuelve a ejecutar "
                "manage.py crear_usuario_mysql."
            )
        else:
            self.bien(f"Entra con la cuenta «{usuario}», no con root.")

        try:
            with connection.cursor() as cursor:
                cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
                permisos = [fila[0] for fila in cursor.fetchall()]
                cursor.execute("SHOW VARIABLES LIKE 'skip_networking'")
                red = (cursor.fetchone() or ("", "ON"))[1]
                cursor.execute("SHOW VARIABLES LIKE 'bind_address'")
                direccion = (cursor.fetchone() or ("", ""))[1]
        except Exception as exc:  # noqa: BLE001 - se informa y se sigue
            self.ojo(f"No se pudieron leer los permisos de MySQL: {exc}")
            return

        peligrosos = ("ALL PRIVILEGES", "DROP", "ALTER", "CREATE", "SUPER",
                      "GRANT OPTION", "TRIGGER", "FILE")
        encontrados = sorted({
            palabra
            for linea in permisos
            for palabra in peligrosos
            # El permiso vacío USAGE no cuenta; lo que importa es lo que
            # va antes de «ON», que es la lista de lo que puede hacer.
            if palabra in linea.split(" ON ")[0]
        })
        if encontrados:
            self.ojo(
                "La cuenta puede " + ", ".join(p.lower() for p in encontrados)
                + ". La aplicación no lo necesita para funcionar."
            )
        else:
            self.bien("Solo puede leer y escribir filas; no cambiar la estructura.")

        if red.upper() == "ON":
            self.bien("MySQL no escucha en la red: solo se conecta desde esta PC.")
        elif direccion in ("127.0.0.1", "localhost", "::1"):
            self.bien(f"MySQL escucha solo en {direccion}.")
        else:
            self.ojo(
                "MySQL acepta conexiones desde toda la red (puerto 3306 "
                "abierto). El sistema no lo necesita: la aplicación y la base "
                "están en la misma PC, y los celulares entran por el puerto "
                "8000. Para cerrarlo, en el my.ini de XAMPP, sección "
                "[mysqld]:  bind-address=127.0.0.1"
            )

    def revisar_respaldos(self):
        """
        Cuándo se copió la base por última vez.

        Ninguna contraseña protege de un disco que falla, y la asistencia es
        lo que respalda una inhabilitación.
        """
        self.titulo("RESPALDOS")

        carpeta = pathlib.Path(settings.BASE_DIR) / "respaldos"
        copias = sorted(carpeta.glob("asistencia_unap_*.sql")) if carpeta.is_dir() else []
        if not copias:
            self.ojo(
                "No hay ninguna copia de seguridad. Hazla con:  "
                "manage.py respaldar"
            )
            return

        ultima = max(copias, key=lambda p: p.stat().st_mtime)
        cuando = datetime.datetime.fromtimestamp(ultima.stat().st_mtime)
        dias = (datetime.datetime.now() - cuando).days
        self.dato(f"{len(copias)} copia(s). La última: {cuando:%d/%m/%Y %H:%M}.")
        if dias > 7:
            self.ojo(
                f"La copia más reciente tiene {dias} días. Conviene una por "
                "semana, al cerrar la semana de clases."
            )
        else:
            self.bien("Hay una copia reciente.")

    def revisar_cuentas(self):
        self.titulo("CUENTAS")

        admins = list(Usuario.objects.filter(rol=Usuario.Rol.ADMIN, is_active=True))
        if not admins:
            self.mal("No hay ningún administrador activo: nadie podría gestionar el sistema.")
        else:
            self.bien(
                f"{len(admins)} administrador(es): "
                + ", ".join(u.username for u in admins)
            )

        sin_clave = Usuario.objects.filter(password=CLAVE_SIN_DEFINIR)
        if sin_clave.exists():
            self.ojo(
                f"{sin_clave.count()} cuenta(s) sin contraseña definida: "
                + ", ".join(sin_clave.values_list("username", flat=True))
            )
        else:
            self.bien("Todas las cuentas tienen contraseña.")

        de_reparto = Usuario.objects.filter(debe_cambiar_clave=True, is_active=True)
        if de_reparto.exists():
            self.dato(
                f"{de_reparto.count()} cuenta(s) con una clave puesta por el "
                "administrador: " + ", ".join(de_reparto.values_list("username", flat=True))
                + ". El sistema les pedirá una propia al entrar."
            )

        # La clave de reparto del docente es su DNI. Solo es un problema si
        # además está dada por buena: entonces nadie va a pedirle que la
        # cambie, y quien conozca el DNI entra en su nombre y firma
        # asistencia por él. Si está marcada como pendiente, el sistema ya
        # se encarga y no hay nada que hacer.
        sin_resolver = [
            d for d in Docente.objects.select_related("usuario").exclude(dni=None)
            if d.usuario
            and not d.usuario.debe_cambiar_clave
            and d.usuario.check_password(d.dni or "")
        ]
        if sin_resolver:
            self.ojo(
                f"{len(sin_resolver)} docente(s) tienen su DNI como contraseña "
                "definitiva: " + ", ".join(d.usuario.username for d in sin_resolver)
                + ". Asígnales una nueva en Administración; el sistema les "
                "pedirá elegir la suya al entrar."
            )
        else:
            self.bien("Ningún docente tiene su DNI dado por contraseña definitiva.")

        huerfanos = Usuario.objects.filter(
            rol=Usuario.Rol.DOCENTE, ficha_docente__isnull=True
        )
        if huerfanos.exists():
            self.ojo(
                f"{huerfanos.count()} cuenta(s) de docente sin ficha asociada: "
                + ", ".join(huerfanos.values_list("username", flat=True))
                + ". No pueden llamar asistencia."
            )

    def revisar_registro(self, dias):
        self.titulo(f"REGISTRO DE LOS ÚLTIMOS {dias} DÍAS")

        desde = timezone.now() - timedelta(days=dias)
        try:
            eventos = EventoSeguridad.objects.filter(momento__gte=desde)
            total = eventos.count()
        except Exception as exc:  # noqa: BLE001 - la tabla puede no existir aún
            self.mal(
                "No se pudo leer `evento_seguridad`. Vuelve a importar "
                f"base_de_datos/asistencia_unap_instalar.sql. ({exc})"
            )
            return

        if not total:
            self.dato("Sin anotaciones en el periodo.")
            return

        entradas = eventos.filter(tipo=Evento.LOGIN_OK).count()
        fallos = eventos.filter(tipo=Evento.LOGIN_FALLIDO).count()
        bloqueos = eventos.filter(tipo=Evento.LOGIN_BLOQUEADO).count()
        self.dato(f"{entradas} entradas · {fallos} intentos fallidos · {bloqueos} bloqueos")

        if bloqueos:
            self.ojo(f"{bloqueos} acceso(s) bloqueados por exceso de intentos.")

        # Una IP con muchos fallos y ninguna entrada correcta no es alguien
        # que se equivoca al escribir.
        sospechosas = (
            eventos.filter(tipo=Evento.LOGIN_FALLIDO)
            .values("ip")
            .annotate(veces=Count("id_evento"))
            .filter(veces__gte=LIMITE_POR_USUARIO)
            .order_by("-veces")
        )
        for fila in sospechosas:
            self.ojo(f"{fila['veces']} intentos fallidos desde {fila['ip'] or 'IP desconocida'}.")
        if not sospechosas:
            self.bien("Ningún equipo acumula intentos fallidos.")

        cambios = eventos.exclude(
            tipo__in=[Evento.LOGIN_OK, Evento.LOGIN_FALLIDO, Evento.LOGIN_BLOQUEADO, Evento.SALIDA]
        ).count()
        self.dato(f"{cambios} cambio(s) hechos en el sistema (ver /seguridad/).")

    def resumen(self):
        self.stdout.write("")
        if self.problemas:
            self.stdout.write(self.style.ERROR(
                f"{self.problemas} problema(s) que hay que corregir antes de "
                f"abrir el sistema, y {self.avisos} aviso(s)."
            ))
        elif self.avisos:
            self.stdout.write(self.style.WARNING(
                f"Sin problemas graves. {self.avisos} aviso(s) para revisar."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("Todo en orden."))
