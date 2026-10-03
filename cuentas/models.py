"""
Modelos de cuentas y docentes.

Mapean tablas existentes de `asistencia_unap`: NO se administran con
migraciones (`managed = False`) y respetan nombres de columna del script SQL.
"""
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class Usuario(AbstractBaseUser):
    """Tabla `usuario`. Sin PermissionsMixin: la autorización se basa en `rol`."""

    class Rol(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        DOCENTE = "DOCENTE", "Docente"

    id_usuario = models.AutoField(primary_key=True, db_column="id_usuario")
    username = models.CharField(max_length=50, unique=True, db_column="username")
    # AbstractBaseUser define `password`; aquí lo apuntamos a la columna real.
    password = models.CharField(max_length=255, db_column="password_hash")
    rol = models.CharField(
        max_length=10, choices=Rol.choices, default=Rol.DOCENTE, db_column="rol"
    )
    is_active = models.BooleanField(default=True, db_column="activo")
    last_login = models.DateTimeField(null=True, blank=True, db_column="ultimo_acceso")
    creado_en = models.DateTimeField(auto_now_add=True, db_column="creado_en")
    # TRUE cuando la clave la eligió otra persona. Mientras lo esté, el
    # sistema no deja pasar de «Mi cuenta» (ver config.middleware).
    debe_cambiar_clave = models.BooleanField(
        default=False, db_column="debe_cambiar_clave"
    )

    # BaseUserManager aporta `get_by_natural_key`, que es lo único que
    # necesita el backend de autenticación. Las cuentas se crean con los
    # comandos `crear_admin` y `set_password`, no con `createsuperuser`.
    objects = BaseUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        managed = False
        db_table = "usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.username

    # -- Contraseñas ---------------------------------------------------
    def poner_clave_de_reparto(self, clave):
        """
        Guarda una clave que eligió OTRA persona (el administrador).

        Queda marcada como pendiente de cambio: una clave que conocen dos
        personas no identifica a ninguna, y la asistencia se firma a
        nombre del docente. Al entrar, el sistema le pedirá la suya.
        """
        self.set_password(clave)
        self.debe_cambiar_clave = True

    def poner_clave_propia(self, clave):
        """Guarda la clave que eligió su dueño: ya no hay nada pendiente."""
        self.set_password(clave)
        self.debe_cambiar_clave = False

    # -- Ayudas de rol -------------------------------------------------
    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN

    @property
    def docente(self):
        """Ficha de docente asociada, o None si la cuenta es solo administrativa."""
        return getattr(self, "ficha_docente", None)

    @property
    def nombre_completo(self):
        ficha = self.docente
        if ficha:
            return ficha.nombre_completo
        return self.username

    @property
    def iniciales(self):
        """Dos letras para el avatar de la barra superior."""
        partes = self.nombre_completo.split()
        if not partes:
            return "?"
        if len(partes) == 1:
            return partes[0][:2].upper()
        return (partes[0][0] + partes[1][0]).upper()


class Docente(models.Model):
    """Tabla `docente`."""

    id_docente = models.AutoField(primary_key=True, db_column="id_docente")
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="id_usuario",
        null=True,
        blank=True,
        related_name="ficha_docente",
    )
    dni = models.CharField(max_length=8, null=True, blank=True, db_column="dni")
    apellidos = models.CharField(max_length=100, db_column="apellidos")
    nombres = models.CharField(max_length=100, db_column="nombres")
    email = models.EmailField(max_length=120, null=True, blank=True, db_column="email")
    activo = models.BooleanField(default=True, db_column="activo")

    class Meta:
        managed = False
        db_table = "docente"
        ordering = ["apellidos", "nombres"]
        verbose_name = "docente"
        verbose_name_plural = "docentes"

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        return f"{self.apellidos} {self.nombres}".strip()


def docente_por_id(valor, *, solo_activos=False):
    """
    Busca un docente por id tolerando lo que llegue de un formulario.

    Los `<select>` mandan texto: si el valor no es un número (formulario
    manipulado o campo vacío) devolvemos None en vez de dejar que Django
    reviente con ValueError y la pantalla acabe en un error 500.
    """
    try:
        id_docente = int(valor)
    except (TypeError, ValueError):
        return None

    consulta = Docente.objects.filter(pk=id_docente)
    if solo_activos:
        consulta = consulta.filter(activo=True)
    return consulta.first()
