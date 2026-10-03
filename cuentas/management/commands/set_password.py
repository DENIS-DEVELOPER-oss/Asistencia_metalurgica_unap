"""
Asigna la contraseña de un usuario existente de la tabla `usuario`.

El script SQL deja las cuentas con `password_hash = 'PENDIENTE_DEFINIR'`,
que no es un hash válido y por tanto impide iniciar sesión. Este comando
guarda un hash real generado por Django.

Uso:
    python manage.py set_password ralvarez
    python manage.py set_password ralvarez --password "MiClaveSegura123"
    python manage.py set_password ralvarez --password "..." --sin-validar
    python manage.py set_password admin --sin-forzar

La clave queda marcada como pendiente de cambio: quien entre con ella
tendrá que elegir la suya antes de hacer nada más, porque una clave que
conocen dos personas no identifica a ninguna. Con `--sin-forzar` no se
marca, que es lo que hace falta cuando uno se pone su propia clave para
recuperar el acceso.
"""
from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from cuentas.models import Usuario


class Command(BaseCommand):
    help = "Asigna (o cambia) la contraseña de un usuario de la tabla `usuario`."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Nombre de usuario, por ejemplo: ralvarez")
        parser.add_argument(
            "--password",
            dest="password",
            default=None,
            help="Contraseña en texto plano. Si se omite, se pide de forma interactiva.",
        )
        parser.add_argument(
            "--sin-forzar",
            action="store_true",
            dest="sin_forzar",
            help="No exige que su dueño la cambie al entrar (para tu propia cuenta).",
        )
        parser.add_argument(
            "--sin-validar",
            action="store_true",
            dest="sin_validar",
            help="Omite las reglas de robustez de contraseña de Django.",
        )

    def handle(self, *args, **opciones):
        username = opciones["username"].strip()
        usuario = Usuario.objects.filter(username=username).first()
        if usuario is None:
            existentes = ", ".join(
                Usuario.objects.values_list("username", flat=True).order_by("username")
            )
            raise CommandError(
                f"No existe el usuario «{username}». Usuarios registrados: {existentes or '(ninguno)'}"
            )

        clave = opciones["password"]
        if not clave:
            clave = getpass(f"Nueva contraseña para «{username}»: ")
            confirmacion = getpass("Repite la contraseña: ")
            if clave != confirmacion:
                raise CommandError("Las contraseñas no coinciden.")

        if not clave:
            raise CommandError("La contraseña no puede estar vacía.")

        if not opciones["sin_validar"]:
            try:
                validate_password(clave, usuario)
            except ValidationError as exc:
                mensajes = "\n  - ".join(exc.messages)
                raise CommandError(
                    f"La contraseña no cumple las reglas de seguridad:\n  - {mensajes}\n"
                    "Usa --sin-validar si aun así quieres asignarla."
                ) from exc

        if opciones["sin_forzar"]:
            usuario.poner_clave_propia(clave)
        else:
            usuario.poner_clave_de_reparto(clave)
        usuario.save(update_fields=["password", "debe_cambiar_clave"])

        ficha = usuario.docente
        detalle = f" ({ficha.nombre_completo})" if ficha else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Contraseña actualizada para «{username}»{detalle}. Rol: {usuario.rol}."
            )
        )
        if usuario.debe_cambiar_clave:
            self.stdout.write(
                "Al entrar tendrá que elegir una contraseña propia. "
                "Usa --sin-forzar si no quieres que se le pida."
            )
