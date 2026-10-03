"""Páginas de error con el diseño del sistema."""
from django.shortcuts import render


def pagina_no_encontrada(request, exception=None):
    return render(
        request,
        "error.html",
        {
            "codigo": "404",
            "titulo": "No encontramos esa página",
            "mensaje": "Es posible que el enlace haya cambiado o esté mal escrito.",
        },
        status=404,
    )


def acceso_denegado(request, exception=None):
    return render(
        request,
        "error.html",
        {
            "codigo": "403",
            "titulo": "No tienes acceso a esta página",
            "mensaje": (
                str(exception)
                or "Esta sección está reservada para el administrador del sistema."
            ),
        },
        status=403,
    )


def error_del_servidor(request):
    return render(
        request,
        "error.html",
        {
            "codigo": "500",
            "titulo": "Ocurrió un error inesperado",
            "mensaje": "Vuelve a intentarlo. Si el problema sigue, avisa al administrador.",
        },
        status=500,
    )
