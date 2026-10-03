"""Datos que necesitan todas las plantillas."""
from academico.acceso import grupos_en_cache


def grupos_del_usuario(request):
    """
    Lista de grupos del docente para el selector de la barra superior.

    Permite saltar de un curso a otro sin volver al inicio. Es una sola
    consulta por petición (compartida con las vistas que también los
    necesitan) y solo se ejecuta si hay sesión iniciada.
    """
    usuario = getattr(request, "user", None)
    if not (usuario and usuario.is_authenticated):
        return {"grupos_usuario": []}
    return {"grupos_usuario": grupos_en_cache(request)}
