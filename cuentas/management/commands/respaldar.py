"""
Copia de seguridad de la base de datos.

La asistencia es el registro oficial del curso: es lo que respalda una
inhabilitación. Un disco que falla, un `DROP DATABASE` de más o un equipo
robado se llevan el ciclo entero, y eso no lo evita ninguna contraseña.

Guarda un archivo con la fecha y la hora en la carpeta `respaldos/`, y
borra los más viejos para que no crezca sin fin.

Uso:
    python manage.py respaldar
    python manage.py respaldar --carpeta D:/copias
    python manage.py respaldar --conservar 20

PARA RESTAURAR (desde la ventana negra, en la carpeta del proyecto):

    1. mysql -u root -e "DROP DATABASE asistencia_unap"
    2. mysql -u root < base_de_datos/asistencia_unap_instalar.sql
    3. mysql -u root asistencia_unap < respaldos/EL_ARCHIVO.sql

El paso 2 no se puede saltar: el respaldo trae las tablas y sus datos,
mientras que los procedimientos, los disparadores y las vistas vienen del
instalador, que es donde se escriben.
"""
import datetime
import pathlib
import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ._herramientas_mysql import buscar_programa

CONSERVAR_POR_DEFECTO = 10


class Command(BaseCommand):
    help = "Guarda una copia de seguridad de la base de datos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--carpeta", default=None,
            help="Dónde guardarla (por defecto, la carpeta «respaldos» del proyecto).",
        )
        parser.add_argument(
            "--conservar", type=int, default=CONSERVAR_POR_DEFECTO,
            help=f"Cuántas copias se guardan antes de borrar las viejas "
                 f"(por defecto {CONSERVAR_POR_DEFECTO}; 0 = todas).",
        )
        parser.add_argument(
            "--usuario", default=None,
            help="Cuenta de MySQL para el volcado (por defecto, la del .env).",
        )
        parser.add_argument(
            "--clave", default=None,
            help="Contraseña de esa cuenta.",
        )

    def handle(self, *args, **opciones):
        base = settings.DATABASES["default"]
        programa = buscar_programa("mysqldump")
        if programa is None:
            raise CommandError(
                "No se encontró mysqldump. Suele estar en la carpeta de XAMPP, "
                "por ejemplo D:/xampp/mysql/bin. Comprueba que XAMPP esté "
                "instalado."
            )

        carpeta = pathlib.Path(opciones["carpeta"] or pathlib.Path(settings.BASE_DIR) / "respaldos")
        carpeta.mkdir(parents=True, exist_ok=True)

        momento = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        destino = carpeta / f"asistencia_unap_{momento}.sql"

        orden = [
            str(programa),
            f"--host={base['HOST'] or '127.0.0.1'}",
            f"--port={base['PORT'] or 3306}",
            f"--user={opciones['usuario'] or base['USER']}",
            "--default-character-set=utf8mb4",
            "--single-transaction",       # no bloquea el sistema mientras copia
            "--skip-triggers",            # vienen del instalador
            "--skip-routines",            # idem: procedimientos y funciones
            "--databases", base["NAME"],
        ]
        clave = opciones["clave"] if opciones["clave"] is not None else base["PASSWORD"]
        if clave:
            # Va por el entorno y no en la línea de comandos, donde cualquiera
            # que liste los procesos de la PC podría leerla.
            entorno_clave = {"MYSQL_PWD": clave}
        else:
            entorno_clave = {}

        import os

        entorno = {**os.environ, **entorno_clave}

        self.stdout.write(f"Copiando «{base['NAME']}» …")
        try:
            with destino.open("wb") as archivo:
                resultado = subprocess.run(
                    orden, stdout=archivo, stderr=subprocess.PIPE, env=entorno, check=False
                )
        except OSError as exc:
            raise CommandError(f"No se pudo ejecutar mysqldump: {exc}") from exc

        if resultado.returncode != 0:
            destino.unlink(missing_ok=True)
            raise CommandError(
                "mysqldump falló y no se guardó nada:\n"
                + resultado.stderr.decode("utf-8", "replace").strip()
            )

        tamano = destino.stat().st_size
        if tamano < 1024:
            destino.unlink(missing_ok=True)
            raise CommandError(
                "El archivo salió vacío, así que no sirve de respaldo. "
                "Comprueba que la cuenta de MySQL pueda leer la base."
            )

        self.stdout.write(self.style.SUCCESS(
            f"Guardado: {destino}  ({tamano / 1024:.0f} KB)"
        ))
        self.podar(carpeta, opciones["conservar"])
        self.stdout.write(
            "Llévate una copia a otro disco o a la nube: un respaldo que vive "
            "en la misma PC no sirve si es la PC lo que se pierde."
        )

    def podar(self, carpeta, conservar):
        """Borra las copias más antiguas; sin esto la carpeta crece sin freno."""
        if conservar <= 0:
            return
        copias = sorted(carpeta.glob("asistencia_unap_*.sql"))
        sobran = copias[:-conservar] if len(copias) > conservar else []
        for vieja in sobran:
            vieja.unlink()
        if sobran:
            self.stdout.write(
                f"Se borraron {len(sobran)} copia(s) antigua(s); se conservan las "
                f"{conservar} más recientes."
            )
