"""
Crea (o convierte en administrador) una cuenta con rol ADMIN.

El script SQL solo incluye la cuenta de la docente; el panel de
administración necesita al menos un usuario con rol ADMIN.

Uso:
    python manage.py crear_admin admin
    python manage.py crear_admin admin --password "ClaveSegura123"
"""
from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from cuentas.models import Usuario


class Command(BaseCommand):
    help = "Crea una cuenta con rol ADMIN o promueve una existente."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Nombre de usuario del administrador")
        parser.add_argument("--password", dest="password", default=None)
        parser.add_argument("--sin-validar", action="store_true", dest="sin_validar")

    def handle(self, *args, **opciones):
        username = opciones["username"].strip()
        if not username:
            raise CommandError("El nombre de usuario no puede estar vacío.")

        clave = opciones["password"]
        if not clave:
            clave = getpass(f"Contraseña para «{username}»: ")
            if clave != getpass("Repite la contraseña: "):
                raise CommandError("Las contraseñas no coinciden.")
        if not clave:
            raise CommandError("La contraseña no puede estar vacía.")

        if not opciones["sin_validar"]:
            try:
                validate_password(clave)
            except ValidationError as exc:
                mensajes = "\n  - ".join(exc.messages)
                raise CommandError(
                    f"La contraseña no cumple las reglas de seguridad:\n  - {mensajes}"
                ) from exc

        usuario = Usuario.objects.filter(username=username).first()
        if usuario is None:
            usuario = Usuario(username=username, rol=Usuario.Rol.ADMIN, is_active=True)
            accion = "creada"
        else:
            usuario.rol = Usuario.Rol.ADMIN
            usuario.is_active = True
            accion = "actualizada"

        # Quien ejecuta este comando es quien va a entrar con la cuenta,
        # así que la clave ya es suya: no hay nada que pedirle al entrar.
        usuario.poner_clave_propia(clave)
        usuario.save()

        self.stdout.write(
            self.style.SUCCESS(f"Cuenta ADMIN «{username}» {accion} correctamente.")
        )
