"""
Capa de servicio del llamado de asistencia.

Toda la escritura pasa OBLIGATORIAMENTE por los procedimientos almacenados
de `asistencia_unap` (`sp_iniciar_sesion`, `sp_marcar_asistencia`,
`sp_cerrar_sesion`), invocados con `connection.cursor().callproc(...)`.
Los errores `SIGNAL SQLSTATE '45000'` de triggers y procedimientos se
traducen a `ErrorDeNegocio` (HTTP 400) con el texto que emite la base.
"""
import logging

from django.db import Error as DatabaseError
from django.db import connection, transaction

from .errores import ErrorDeNegocio, mensaje_de_error_mysql
from .models import Asistencia, EstadoAsistencia, SesionClase

logger = logging.getLogger(__name__)

ESTADOS_VALIDOS = {estado.value for estado in EstadoAsistencia}


def _vaciar_resultados(cursor):
    """Consume los conjuntos de resultados que deja `CALL` en la conexión."""
    try:
        while cursor.nextset():
            pass
    except Exception:  # noqa: BLE001 - el driver ya no tiene resultados pendientes
        pass


def iniciar_sesion_clase(id_grupo, id_docente, fecha, hora_inicio, tema=None):
    """
    Llama a `sp_iniciar_sesion` y devuelve el id de la sesión creada.

    El procedimiento valida que el docente esté asignado al grupo y crea la
    lista completa de matriculados activos con estado FALTA por defecto.
    """
    try:
        with connection.cursor() as cursor:
            cursor.callproc(
                "sp_iniciar_sesion",
                [id_grupo, id_docente, fecha, hora_inicio, tema, 0],
            )
            _vaciar_resultados(cursor)
            # El sexto parámetro (índice 5) es el OUT p_id_sesion.
            cursor.execute("SELECT @_sp_iniciar_sesion_5")
            fila = cursor.fetchone()
    except DatabaseError as exc:
        logger.warning("sp_iniciar_sesion falló: %s", exc)
        raise ErrorDeNegocio(mensaje_de_error_mysql(exc)) from exc

    if not fila or fila[0] is None:
        raise ErrorDeNegocio(
            "La base de datos no devolvió el identificador de la sesión de clase."
        )
    return int(fila[0])


def _normalizar_estado(estado):
    """Deja el estado en mayúsculas y comprueba que sea uno de los cuatro válidos."""
    estado = (estado or "").strip().upper()
    if estado not in ESTADOS_VALIDOS:
        raise ErrorDeNegocio(
            f"Estado de asistencia no válido: '{estado}'. "
            f"Valores permitidos: {', '.join(sorted(ESTADOS_VALIDOS))}."
        )
    return estado


def _revisar_lote(id_sesion, marcas):
    """
    Valida el lote entero antes de tocar la base y devuelve {id_matricula: estado}.

    La pertenencia de todos los alumnos a la sesión se comprueba con UNA sola
    consulta: con 40 alumnos en clase, hacerlo uno por uno significaba 40
    consultas extra por cada guardado.
    """
    estados = {}
    for marca in marcas:
        estados[marca["id_matricula"]] = _normalizar_estado(marca["estado"])

    de_la_sesion = set(
        Asistencia.objects.filter(
            sesion_id=id_sesion, matricula_id__in=list(estados)
        ).values_list("matricula_id", flat=True)
    )
    ajenos = set(estados) - de_la_sesion
    if ajenos:
        raise ErrorDeNegocio(
            f"{len(ajenos)} estudiante(s) no forman parte de la lista de esta "
            "sesión de clase; vuelve a cargar la página e inténtalo de nuevo."
        )
    return estados


def _ejecutar_marca(id_sesion, id_matricula, estado, observacion):
    """Una llamada a `sp_marcar_asistencia`."""
    try:
        with connection.cursor() as cursor:
            cursor.callproc(
                "sp_marcar_asistencia",
                [id_sesion, id_matricula, estado, observacion],
            )
            _vaciar_resultados(cursor)
    except DatabaseError as exc:
        logger.warning("sp_marcar_asistencia falló: %s", exc)
        raise ErrorDeNegocio(mensaje_de_error_mysql(exc)) from exc


def marcar_asistencia_en_lote(id_sesion, marcas):
    """
    Aplica una lista de marcas en una sola transaccion.

    `marcas` es una lista de diccionarios con las claves `id_matricula`,
    `estado` y, opcionalmente, `observacion`. Si una falla, no se aplica
    ninguna.
    """
    if not marcas:
        raise ErrorDeNegocio("No se recibió ninguna marca de asistencia.")

    estados = _revisar_lote(id_sesion, marcas)

    with transaction.atomic():
        for marca in marcas:
            id_matricula = marca["id_matricula"]
            observacion = (marca.get("observacion") or "").strip() or None
            _ejecutar_marca(id_sesion, id_matricula, estados[id_matricula], observacion)
    return len(marcas)


def cerrar_sesion_clase(id_sesion):
    """Llama a `sp_cerrar_sesion`; a partir de aquí la sesión es de solo lectura."""
    sesion = SesionClase.objects.filter(pk=id_sesion).first()
    if sesion is None:
        raise ErrorDeNegocio("La sesión de clase no existe.")
    if not sesion.esta_abierta:
        raise ErrorDeNegocio("La sesión de clase ya estaba cerrada.")

    try:
        with connection.cursor() as cursor:
            cursor.callproc("sp_cerrar_sesion", [id_sesion])
            _vaciar_resultados(cursor)
    except DatabaseError as exc:
        logger.warning("sp_cerrar_sesion falló: %s", exc)
        raise ErrorDeNegocio(mensaje_de_error_mysql(exc)) from exc
