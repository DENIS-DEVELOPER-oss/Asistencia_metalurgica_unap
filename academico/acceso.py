"""
Control de acceso a grupos.

Reglas:

- Un DOCENTE ve y opera los grupos donde `grupo.id_docente` coincide con su
  propia ficha. Un ADMIN los ve todos.
- Consultar (historial, reporte, matriculados) lo puede hacer cualquiera de
  los dos. Llamar asistencia, no: eso queda reservado al docente titular
  del grupo, porque la sesión se firma a su nombre.
"""
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404

from .models import Grupo

RELACIONES = ("curso", "curso__escuela", "curso__escuela__facultad", "periodo", "docente")


def grupos_visibles(usuario):
    """QuerySet de grupos que el usuario puede consultar."""
    consulta = Grupo.objects.select_related(*RELACIONES)
    if usuario.es_admin:
        return consulta
    ficha = usuario.docente
    if ficha is None:
        return consulta.none()
    return consulta.filter(docente_id=ficha.id_docente)


def grupos_en_cache(request):
    """
    Los mismos grupos de `grupos_visibles`, calculados una sola vez por petición.

    La barra superior los pinta en todas las pantallas (a través del context
    processor) y algunas vistas los necesitan otra vez; guardarlos en la
    petición evita repetir la consulta.
    """
    if not hasattr(request, "_grupos_visibles"):
        request._grupos_visibles = list(grupos_visibles(request.user))
    return request._grupos_visibles


def obtener_grupo(usuario, id_grupo):
    """Devuelve el grupo o corta con 404/403 según corresponda."""
    grupo = Grupo.objects.select_related(*RELACIONES).filter(pk=id_grupo).first()
    if grupo is None:
        raise Http404("El grupo solicitado no existe.")

    if usuario.es_admin:
        return grupo

    ficha = usuario.docente
    if ficha is None or grupo.docente_id != ficha.id_docente:
        raise PermissionDenied("No tienes asignado este grupo.")
    return grupo


def docente_del_usuario(usuario):
    """Ficha de docente del usuario autenticado; error claro si no la tiene."""
    ficha = usuario.docente
    if ficha is None:
        raise PermissionDenied(
            "Tu cuenta no está vinculada a una ficha de docente; "
            "pide a un administrador que la asocie."
        )
    return ficha


def es_docente_titular(usuario, grupo):
    """
    ¿Este usuario es el docente asignado al grupo?

    Sin excepción, para decidir qué botones se pintan en pantalla.
    """
    ficha = usuario.docente
    return ficha is not None and grupo.docente_id == ficha.id_docente


def docente_titular(usuario, grupo):
    """
    Ficha del usuario, solo si es el docente asignado al grupo.

    Llamar asistencia es un acto del docente que dicta la clase: queda
    firmado a su nombre en `sesion_clase.id_docente` y es el registro
    oficial del curso. Por eso no lo hace nadie en su lugar, tampoco el
    administrador; lo que el administrador puede hacer es reasignar el
    grupo a otro docente.
    """
    if not es_docente_titular(usuario, grupo):
        raise PermissionDenied(
            "Solo el docente asignado a este curso puede llamar asistencia. "
            "Si hace falta cambiarlo, hazlo desde Administración → "
            "«Grupos y docente asignado»."
        )
    return usuario.docente


def es_admin(usuario):
    return bool(usuario.is_authenticated and usuario.es_admin)


def solo_admin(vista):
    """
    Restringe una vista a cuentas ADMIN.

    Crear, editar o eliminar cursos y matrículas es tarea del administrador;
    el docente solo consulta y llama asistencia.
    """

    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not es_admin(request.user):
            raise PermissionDenied(
                "Solo un administrador puede gestionar cursos y matrículas."
            )
        return vista(request, *args, **kwargs)

    return envoltura
