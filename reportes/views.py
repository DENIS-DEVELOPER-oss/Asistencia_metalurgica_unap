"""Reporte de asistencia en pantalla y exportación a Excel, Word y PDF."""
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from academico.acceso import es_docente_titular, grupos_en_cache, obtener_grupo
from asistencia.views import obtener_sesion

from .datos import construir_reporte, datos_de_sesion
from .excel import generar_excel, generar_excel_general, generar_excel_sesion
from .pdf import generar_pdf_reporte, generar_pdf_sesion
from .word import generar_word, generar_word_sesion

TIPO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TIPO_WORD = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TIPO_PDF = "application/pdf"

# Cada curso del consolidado cuesta varias consultas pesadas. Con una cuenta
# ADMIN, `grupos_visibles` devuelve TODOS los grupos de la universidad, así
# que el Excel se pediría sobre cientos de cursos y el navegador agotaría el
# tiempo de espera. Por encima de este número pedimos abrir curso por curso.
MAXIMO_CURSOS_CONSOLIDADO = 40

# Reporte de un grupo: (extensión, tipo MIME, función generadora)
FORMATOS_GRUPO = {
    "excel": ("xlsx", TIPO_EXCEL, generar_excel),
    "word": ("docx", TIPO_WORD, generar_word),
    "pdf": ("pdf", TIPO_PDF, generar_pdf_reporte),
}

# Lista de una sola clase
FORMATOS_SESION = {
    "excel": ("xlsx", TIPO_EXCEL, generar_excel_sesion),
    "word": ("docx", TIPO_WORD, generar_word_sesion),
    "pdf": ("pdf", TIPO_PDF, generar_pdf_sesion),
}


def _descarga(contenido, nombre, tipo):
    respuesta = HttpResponse(contenido, content_type=tipo)
    respuesta["Content-Disposition"] = (
        f'attachment; filename="{nombre}"; filename*=UTF-8\'\'{quote(nombre)}'
    )
    respuesta["Content-Length"] = str(len(contenido))
    return respuesta


@login_required
def reporte(request, id_grupo):
    """Tabla de resumen por alumno con barra de porcentaje y semáforo."""
    grupo = obtener_grupo(request.user, id_grupo)
    datos = construir_reporte(grupo)
    solo_riesgo = request.GET.get("riesgo") == "1"

    alumnos = datos["alumnos"]
    if solo_riesgo:
        alumnos = [a for a in alumnos if a["en_riesgo"]]

    return render(
        request,
        "reporte.html",
        {
            "titulo": "Reporte de asistencia",
            "seccion": "reporte",
            "grupo": grupo,
            "es_titular": es_docente_titular(request.user, grupo),
            "reporte": datos,
            "alumnos": alumnos,
            "solo_riesgo": solo_riesgo,
        },
    )


@login_required
def exportar(request, id_grupo, formato):
    """Descarga del reporte de un grupo en el formato pedido."""
    if formato not in FORMATOS_GRUPO:
        raise Http404("Formato no soportado. Usa excel, word o pdf.")

    grupo = obtener_grupo(request.user, id_grupo)
    extension, tipo, generar = FORMATOS_GRUPO[formato]

    contenido = generar(construir_reporte(grupo))
    nombre = f"{grupo.etiqueta_archivo}_asistencia.{extension}"
    return _descarga(contenido, nombre, tipo)


@login_required
def exportar_sesion(request, id_sesion, formato):
    """Descarga de la lista de asistencia de una sola clase."""
    if formato not in FORMATOS_SESION:
        raise Http404("Formato no soportado. Usa excel, word o pdf.")

    sesion = obtener_sesion(request.user, id_sesion)
    extension, tipo, generar = FORMATOS_SESION[formato]

    contenido = generar(datos_de_sesion(sesion))
    nombre = f"{sesion.grupo.etiqueta_archivo}_{sesion.fecha:%Y-%m-%d}_lista.{extension}"
    return _descarga(contenido, nombre, tipo)


@login_required
def exportar_general(request):
    """
    Excel consolidado con todos los cursos que el usuario puede ver.

    Una hoja «General» con una fila por curso y, después, una hoja por
    curso con su matriz alumno x fecha.
    """
    grupos = list(grupos_en_cache(request))
    if not grupos:
        raise Http404("No tienes cursos asignados.")

    if len(grupos) > MAXIMO_CURSOS_CONSOLIDADO:
        messages.error(
            request,
            f"El consolidado abarca {len(grupos)} cursos y solo se puede generar "
            f"hasta {MAXIMO_CURSOS_CONSOLIDADO}. Descarga el reporte de cada "
            "curso por separado desde su pantalla de reporte.",
        )
        return redirect("cursos")

    reportes = [construir_reporte(grupo) for grupo in grupos]
    # Quien descarga, no quien dicta: el docente de cada curso lo pone
    # `construir_reporte` a partir del grupo. Una cuenta de administrador no
    # tiene ficha de docente y `nombre_completo` cae a su usuario, así que
    # firmar el reporte con ella lo dejaba a nombre de «admin».
    contenido = generar_excel_general(reportes, generado_por=request.user.nombre_completo)

    periodo = grupos[0].periodo.codigo if len(grupos) == 1 else "todos"
    nombre = f"Asistencia_{periodo}_{timezone.now():%Y-%m-%d}_consolidado.xlsx"
    return _descarga(contenido, nombre, TIPO_EXCEL)
