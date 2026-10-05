"""
Registro de seguridad: quién entra, quién lo intenta y qué se cambia.

Dos usos distintos con el mismo apunte:

- **Frenar el tanteo de contraseñas.** La contraseña inicial de un docente
  es su DNI: ocho dígitos que alguien del entorno puede conocer o
  deducir. Sin un límite, probar una lista de DNIs no cuesta nada. Tras
  varios fallos seguidos, la cuenta y la IP quedan en espera.

- **Saber quién hizo qué.** La asistencia es el registro oficial del
  curso. Si aparece un curso borrado o una nota cambiada, hace falta
  poder responder quién y cuándo, no suponerlo.
"""
from datetime import timedelta

from django.db import models
from django.utils import timezone

# Cuántos fallos seguidos se toleran y durante cuánto se cuentan.
LIMITE_POR_USUARIO = 5
LIMITE_POR_IP = 20
VENTANA = timedelta(minutes=15)

# Cuánto se conserva el registro antes de que `limpiar_antiguos` lo pode.
DIAS_QUE_SE_GUARDA = 180


class Evento(models.TextChoices):
    LOGIN_OK = "LOGIN_OK", "Entró al sistema"
    LOGIN_FALLIDO = "LOGIN_FALLIDO", "Intento fallido"
    LOGIN_BLOQUEADO = "LOGIN_BLOQUEADO", "Intento bloqueado"
    SALIDA = "SALIDA", "Cerró sesión"

    CLAVE_PROPIA = "CLAVE_PROPIA", "Cambió su contraseña"
    USUARIO_PROPIO = "USUARIO_PROPIO", "Cambió su nombre de usuario"
    CLAVE_ASIGNADA = "CLAVE_ASIGNADA", "Asignó una contraseña"

    DOCENTE_CREADO = "DOCENTE_CREADO", "Registró un docente"
    DOCENTE_EDITADO = "DOCENTE_EDITADO", "Editó un docente"
    DOCENTE_ELIMINADO = "DOCENTE_ELIMINADO", "Eliminó un docente"

    CURSO_CREADO = "CURSO_CREADO", "Creó un curso"
    CURSO_EDITADO = "CURSO_EDITADO", "Editó un curso"
    CURSO_ELIMINADO = "CURSO_ELIMINADO", "Eliminó un curso"
    DOCENTE_ASIGNADO = "DOCENTE_ASIGNADO", "Asignó un docente a un grupo"
    CLASE_ELIMINADA = "CLASE_ELIMINADA", "Eliminó una clase"

    PERIODO_CREADO = "PERIODO_CREADO", "Creó un periodo"
    ESTUDIANTES = "ESTUDIANTES", "Matriculó estudiantes"
    MATRICULA_QUITADA = "MATRICULA_QUITADA", "Quitó una matrícula"


class EventoSeguridad(models.Model):
    """Tabla `evento_seguridad`. Solo se escribe y se lee; nunca se edita."""

    id_evento = models.AutoField(primary_key=True, db_column="id_evento")
    momento = models.DateTimeField(db_column="momento")
    tipo = models.CharField(max_length=30, choices=Evento.choices, db_column="tipo")
    usuario = models.CharField(max_length=50, null=True, blank=True, db_column="usuario")
    ip = models.CharField(max_length=45, null=True, blank=True, db_column="ip")
    detalle = models.CharField(max_length=255, null=True, blank=True, db_column="detalle")

    class Meta:
        managed = False
        db_table = "evento_seguridad"
        ordering = ["-momento", "-id_evento"]

    def __str__(self):
        return f"{self.momento:%d/%m/%Y %H:%M} {self.tipo} {self.usuario or ''}"

    @property
    def es_sospechoso(self):
        return self.tipo in (Evento.LOGIN_FALLIDO, Evento.LOGIN_BLOQUEADO)

    @property
    def insignia(self):
        """Color de la fila: rojo lo que hay que mirar, gris lo rutinario."""
        if self.tipo == Evento.LOGIN_BLOQUEADO:
            return "ins-rojo"
        if self.tipo == Evento.LOGIN_FALLIDO:
            return "ins-ambar"
        if self.tipo in (Evento.LOGIN_OK, Evento.SALIDA):
            return "ins-gris"
        if "ELIMINAD" in self.tipo or self.tipo == Evento.MATRICULA_QUITADA:
            return "ins-rojo"
        if "CLAVE" in self.tipo or "USUARIO" in self.tipo:
            return "ins-dorado"
        return "ins-marino"


# ---------------------------------------------------------------------
# Escribir
# ---------------------------------------------------------------------
def ip_de(request):
    """
    IP desde la que llega la petición.

    Si algún día el sistema queda detrás de un proxy o balanceador, la IP
    real viaja en `X-Forwarded-For`; sin proxy, esa cabecera la puede
    poner cualquiera, así que solo se mira cuando está declarado.
    """
    from django.conf import settings

    if getattr(settings, "DETRAS_DE_PROXY", False):
        reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if reenviada:
            return reenviada.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "")[:45] or None


def anotar(request, tipo, usuario=None, detalle=None):
    """
    Deja constancia de algo. Nunca interrumpe lo que se estaba haciendo.

    Si la tabla no existiera o la base fallara, eliminar un curso no debe
    fracasar por no poder escribir su apunte: se registra el problema y
    se sigue.
    """
    import logging

    if usuario is None and getattr(request, "user", None) is not None:
        if request.user.is_authenticated:
            usuario = request.user.username

    try:
        EventoSeguridad.objects.create(
            momento=timezone.now(),
            tipo=tipo,
            usuario=(usuario or None) and str(usuario)[:50],
            ip=ip_de(request),
            detalle=(detalle or None) and str(detalle)[:255],
        )
    except Exception:  # noqa: BLE001 - anotar no puede romper la operación
        logging.getLogger(__name__).exception("No se pudo anotar el evento %s", tipo)


# ---------------------------------------------------------------------
# Frenar el tanteo de contraseñas
# ---------------------------------------------------------------------
def _fallos_desde(campo, valor, desde):
    if not valor:
        return 0
    return EventoSeguridad.objects.filter(
        tipo=Evento.LOGIN_FALLIDO, momento__gte=desde, **{campo: valor}
    ).count()


def _ultimo_acierto(usuario):
    """Un inicio de sesión correcto borra la cuenta de fallos anteriores."""
    if not usuario:
        return None
    ultimo = (
        EventoSeguridad.objects.filter(tipo=Evento.LOGIN_OK, usuario=usuario)
        .values_list("momento", flat=True)
        .first()
    )
    return ultimo


def decidir(por_usuario, por_ip, mas_antiguo, ahora):
    """
    La regla, aparte de la base de datos: `(bloqueado, minutos_que_faltan)`.

    Se cuentan por separado los fallos de la cuenta y los del equipo: lo
    primero protege a un docente de que le adivinen su DNI; lo segundo
    impide que alguien recorra una lista de usuarios desde el mismo sitio.

    El bloqueo se levanta solo. `mas_antiguo` es el primer fallo que
    sigue dentro de la ventana: cuando ese caduca, vuelve a haber sitio
    para un intento, así que la espera se mide hasta ahí. Nadie tiene que
    ir a desbloquear nada a mano.
    """
    if por_usuario < LIMITE_POR_USUARIO and por_ip < LIMITE_POR_IP:
        return False, 0
    if mas_antiguo is None:
        return False, 0
    faltan = (mas_antiguo + VENTANA) - ahora
    if faltan.total_seconds() <= 0:
        return False, 0
    return True, max(1, int(faltan.total_seconds() // 60) + 1)


def estado_del_acceso(usuario, ip):
    """Cuenta los fallos recientes de esta cuenta y de este equipo, y decide."""
    ahora = timezone.now()
    desde = ahora - VENTANA

    # Entrar bien borra lo anterior: quien acertó ayer no arrastra los
    # fallos de ayer.
    acierto = _ultimo_acierto(usuario)
    desde_usuario = max(desde, acierto) if acierto else desde

    por_usuario = _fallos_desde("usuario", usuario, desde_usuario)
    por_ip = _fallos_desde("ip", ip, desde)

    if por_usuario >= LIMITE_POR_USUARIO:
        filtro = {"usuario": usuario}
    elif por_ip >= LIMITE_POR_IP:
        filtro = {"ip": ip}
    else:
        return False, 0

    mas_antiguo = (
        EventoSeguridad.objects.filter(
            tipo=Evento.LOGIN_FALLIDO, momento__gte=desde, **filtro
        )
        .order_by("momento")
        .values_list("momento", flat=True)
        .first()
    )
    return decidir(por_usuario, por_ip, mas_antiguo, ahora)


def limpiar_antiguos():
    """Poda lo que ya no sirve. Devuelve cuántos apuntes se borraron."""
    limite = timezone.now() - timedelta(days=DIAS_QUE_SE_GUARDA)
    borrados, _ = EventoSeguridad.objects.filter(momento__lt=limite).delete()
    return borrados
