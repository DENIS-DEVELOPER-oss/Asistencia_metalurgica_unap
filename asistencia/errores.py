"""
Traducción de errores de MySQL (incluidos los SIGNAL SQLSTATE '45000' que
lanzan los triggers y procedimientos) a mensajes claros para el usuario.
"""

# Código que MySQL asigna a un SIGNAL de usuario sin condición declarada.
ERR_SIGNAL_USUARIO = 1644
ERR_DUPLICADO = 1062
ERR_LLAVE_FORANEA = 1452

MENSAJES_POR_CODIGO = {
    ERR_DUPLICADO: (
        "Ya existe un registro con esos datos. "
        "Revisa si la sesión de clase ya fue iniciada a esa misma hora."
    ),
    ERR_LLAVE_FORANEA: "Alguno de los datos enviados no existe en la base de datos.",
}


class ErrorDeNegocio(Exception):
    """Error esperable que se devuelve al cliente como HTTP 400."""


def _desempaquetar(exc):
    """Obtiene (codigo, mensaje) de una excepción de base de datos."""
    candidatos = [exc]
    causa = getattr(exc, "__cause__", None)
    if causa is not None:
        candidatos.append(causa)

    for candidato in candidatos:
        args = getattr(candidato, "args", ())
        if len(args) >= 2 and isinstance(args[0], int):
            return args[0], str(args[1])
    return None, str(exc)


def mensaje_de_error_mysql(exc):
    """Devuelve un mensaje legible en español para una excepción de MySQL."""
    codigo, mensaje = _desempaquetar(exc)

    if codigo == ERR_SIGNAL_USUARIO:
        # El texto del SIGNAL ya viene redactado en español desde la BD.
        return mensaje

    if codigo in MENSAJES_POR_CODIGO:
        return MENSAJES_POR_CODIGO[codigo]

    return f"No se pudo completar la operación en la base de datos: {mensaje}"
