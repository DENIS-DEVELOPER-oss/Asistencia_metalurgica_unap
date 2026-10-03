"""
Crea la cuenta de MySQL con la que trabaja la aplicación.

POR QUÉ HACE FALTA

De fábrica la aplicación entra a MySQL como `root` sin contraseña. Eso
significa que cualquier programa que se ejecute en esta computadora puede
conectarse a la base y cambiar la asistencia ya registrada, saltándose
las reglas del sistema: los disparadores que impiden tocar una clase
cerrada valen para la aplicación, no para quien entra por debajo de ella.

La asistencia es lo que respalda una inhabilitación, así que conviene que
el programa tenga justo los permisos que necesita y ninguno más. Esta
cuenta puede leer y escribir en las tablas de `asistencia_unap`, y nada
más: no puede borrar tablas, ni cambiar su estructura, ni asomarse a
otras bases de datos.

Uso:
    python manage.py crear_usuario_mysql
    python manage.py crear_usuario_mysql --admin-clave "la de root"
    python manage.py crear_usuario_mysql --usuario asistencia_app --clave "..."
    python manage.py crear_usuario_mysql --solo-mostrar

Al terminar deja el usuario y la contraseña escritos en el archivo .env,
así que la aplicación los toma en el siguiente arranque.
"""
import MySQLdb
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ._herramientas_mysql import clave_fuerte, escribir_en_env

# Lo que la aplicación necesita, y nada más.
#
#  - Leer y escribir filas: es lo que hace el sistema.
#  - EXECUTE: el llamado de asistencia pasa por los procedimientos.
#  - SHOW VIEW y LOCK TABLES: para que el respaldo funcione con esta misma
#    cuenta.
#
# Queda fuera a propósito: CREATE, DROP y ALTER (cambiar la estructura),
# TRIGGER (podría quitar las reglas que protegen las clases cerradas),
# GRANT OPTION (darse permisos a sí misma) y cualquier otra base de datos.
PERMISOS = "SELECT, INSERT, UPDATE, DELETE, EXECUTE, SHOW VIEW, LOCK TABLES"

# Desde dónde puede conectarse. La aplicación corre en esta misma PC, así
# que no hace falta permitirle entrar desde la red: si algún día MySQL
# queda expuesto, esta cuenta no sirve para entrar desde fuera.
EQUIPOS = ("localhost", "127.0.0.1")


class Command(BaseCommand):
    help = "Crea en MySQL una cuenta con permisos mínimos para la aplicación."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", default="asistencia_app",
                            help="Nombre de la cuenta a crear (por defecto asistencia_app).")
        parser.add_argument("--clave", default=None,
                            help="Contraseña. Si se omite, se genera una larga al azar.")
        parser.add_argument("--admin-usuario", default="root", dest="admin_usuario",
                            help="Cuenta de MySQL con permiso para crear usuarios.")
        parser.add_argument("--admin-clave", default="", dest="admin_clave",
                            help="Contraseña de esa cuenta (vacía si no tiene).")
        parser.add_argument("--solo-mostrar", action="store_true", dest="solo_mostrar",
                            help="Enseña lo que haría, sin tocar MySQL ni el .env.")

    def handle(self, *args, **opciones):
        base = settings.DATABASES["default"]
        usuario = opciones["usuario"].strip()
        clave = opciones["clave"] or clave_fuerte()

        if not usuario.replace("_", "").isalnum():
            raise CommandError(
                "El nombre de la cuenta solo admite letras, números y «_»."
            )

        sentencias = self.sentencias(usuario, clave, base["NAME"])

        if opciones["solo_mostrar"]:
            self.stdout.write("Esto es lo que se ejecutaría en MySQL:\n")
            for sentencia in sentencias:
                self.stdout.write("  " + sentencia.replace(clave, "********"))
            return

        conexion = self.conectar_como_administrador(base, opciones)
        try:
            cursor = conexion.cursor()
            for sentencia in sentencias:
                cursor.execute(sentencia)
            conexion.commit()
        finally:
            conexion.close()

        self.stdout.write(self.style.SUCCESS(
            f"Cuenta «{usuario}» creada en MySQL con permisos mínimos."
        ))

        self.comprobar(base, usuario, clave)

        ruta = escribir_en_env({"DB_USER": usuario, "DB_PASSWORD": clave})
        self.stdout.write(self.style.SUCCESS(f"Guardada en {ruta}."))
        self.stdout.write("")
        self.stdout.write("Reinicia la aplicación para que la use.")
        self.stdout.write(
            "Para las tareas de administración (importar el instalador, "
            "phpMyAdmin) se sigue usando root: esta cuenta no puede cambiar "
            "la estructura de la base, que es justamente lo que la hace segura."
        )

    # -----------------------------------------------------------------
    def sentencias(self, usuario, clave, base_de_datos):
        """
        Las órdenes que se envían a MySQL, en orden.

        `CREATE OR REPLACE USER` deja el comando repetible: volver a
        ejecutarlo cambia la contraseña en vez de dar error, que es lo que
        hace falta el día que haya que rotarla.
        """
        ordenes = []
        for equipo in EQUIPOS:
            cuenta = f"'{usuario}'@'{equipo}'"
            ordenes += [
                f"CREATE OR REPLACE USER {cuenta} IDENTIFIED BY '{clave}'",
                f"GRANT {PERMISOS} ON `{base_de_datos}`.* TO {cuenta}",
            ]
        ordenes.append("FLUSH PRIVILEGES")
        return ordenes

    def conectar_como_administrador(self, base, opciones):
        try:
            return MySQLdb.connect(
                host=base["HOST"] or "127.0.0.1",
                port=int(base["PORT"] or 3306),
                user=opciones["admin_usuario"],
                passwd=opciones["admin_clave"],
                charset="utf8mb4",
            )
        except MySQLdb.Error as exc:
            raise CommandError(
                f"No se pudo entrar a MySQL como «{opciones['admin_usuario']}»: {exc}\n"
                "Comprueba que MySQL esté encendido en XAMPP y, si root tiene "
                "contraseña, pásala con --admin-clave."
            ) from exc

    def comprobar(self, base, usuario, clave):
        """
        Entra con la cuenta nueva y comprueba que la aplicación funcionará.

        Sin esto, el fallo aparecería en la cara del docente la próxima vez
        que abriera el sistema, y no aquí, donde se puede arreglar.
        """
        try:
            conexion = MySQLdb.connect(
                host=base["HOST"] or "127.0.0.1",
                port=int(base["PORT"] or 3306),
                user=usuario, passwd=clave, db=base["NAME"], charset="utf8mb4",
            )
        except MySQLdb.Error as exc:
            raise CommandError(f"La cuenta nueva no puede conectarse: {exc}") from exc

        try:
            cursor = conexion.cursor()
            # Leer de una tabla y de una vista.
            cursor.execute("SELECT COUNT(*) FROM matricula")
            cursor.execute("SELECT COUNT(*) FROM v_lista_matriculados")
            # Escribir, y deshacerlo: se comprueba el permiso sin dejar rastro.
            cursor.execute("START TRANSACTION")
            cursor.execute(
                "INSERT INTO evento_seguridad (momento, tipo, detalle) "
                "VALUES (NOW(), 'PRUEBA', 'comprobacion de permisos')"
            )
            cursor.execute("ROLLBACK")
            # Y que NO pueda cambiar la estructura.
            puede_borrar = True
            try:
                cursor.execute("DROP TABLE IF EXISTS prueba_de_permisos")
            except MySQLdb.Error:
                puede_borrar = False
        finally:
            conexion.close()

        self.stdout.write("  [ok] puede leer las tablas y las vistas")
        self.stdout.write("  [ok] puede registrar asistencia")
        if puede_borrar:
            self.stdout.write(self.style.WARNING(
                "  [ojo] la cuenta todavía puede borrar tablas; revisa sus permisos"
            ))
        else:
            self.stdout.write("  [ok] no puede borrar ni alterar tablas")
