"""Pantalla de cursos del docente."""
from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q, Window
from django.db.models.functions import RowNumber
from django.shortcuts import redirect, render

from asistencia.models import Asistencia, SesionClase
from cuentas.models import Docente, docente_por_id
# Mismo criterio de color que el reporte y las exportaciones: un solo sitio
# donde se leen SEMAFORO_VERDE y SEMAFORO_AMBAR de settings.
from reportes.datos import clasificar

from .acceso import es_docente_titular, grupos_en_cache, obtener_grupo
from .models import Matricula, VistaListaMatriculados


def estadisticas_de_grupos(ids_grupo):
    """
    Métricas que muestran las tarjetas de «Mis cursos»: alumnos activos,
    clases dictadas, % promedio de asistencia, última clase y sesión abierta.
    """
    stats = {
        id_grupo: {
            "total_alumnos": 0,
            "total_sesiones": 0,
            "porcentaje_promedio": None,
            "ultima_clase": None,
            "sesion_abierta": None,
        }
        for id_grupo in ids_grupo
    }
    if not ids_grupo:
        return stats

    for fila in (
        Matricula.objects.filter(grupo_id__in=ids_grupo, estado=Matricula.Estado.ACTIVA)
        .values("grupo_id")
        .annotate(total=Count("id_matricula"))
    ):
        stats[fila["grupo_id"]]["total_alumnos"] = fila["total"]

    for fila in (
        SesionClase.objects.filter(grupo_id__in=ids_grupo)
        .values("grupo_id")
        .annotate(total=Count("id_sesion"))
    ):
        stats[fila["grupo_id"]]["total_sesiones"] = fila["total"]

    for fila in (
        Asistencia.objects.filter(sesion__grupo_id__in=ids_grupo)
        .values("sesion__grupo_id")
        .annotate(
            total=Count("id_asistencia"),
            asistio=Count("id_asistencia", filter=~Q(estado="FALTA")),
        )
    ):
        total = fila["total"] or 0
        if total:
            stats[fila["sesion__grupo_id"]]["porcentaje_promedio"] = round(
                100 * fila["asistio"] / total, 2
            )

    # Última clase de cada grupo: una sola fila por grupo gracias a la función
    # de ventana, en vez de traerse el historial completo para quedarse con
    # la primera de cada uno.
    ultimas = (
        SesionClase.objects.filter(grupo_id__in=ids_grupo)
        .annotate(
            posicion=Window(
                expression=RowNumber(),
                partition_by=[F("grupo_id")],
                order_by=[F("fecha").desc(), F("hora_inicio").desc()],
            )
        )
        .filter(posicion=1)
    )
    for sesion in ultimas:
        stats[sesion.grupo_id]["ultima_clase"] = sesion

    # Clases abiertas: como máximo una por grupo, son pocas filas.
    for id_grupo, id_sesion in (
        SesionClase.objects.filter(
            grupo_id__in=ids_grupo, estado=SesionClase.Estado.ABIERTA
        )
        .order_by("grupo_id", "-fecha", "-hora_inicio")
        .values_list("grupo_id", "id_sesion")
    ):
        if stats[id_grupo]["sesion_abierta"] is None:
            stats[id_grupo]["sesion_abierta"] = id_sesion

    return stats


def panel_de_docentes(grupos, id_elegido):
    """
    Un botón por docente, con cuántos grupos dicta.

    Se cuenta sobre los grupos ya cargados en la petición, sin consultas
    extra. Los docentes sin ningún grupo también salen: para el
    administrador, saber a quién le falta asignar curso es media faena.
    """
    por_docente = Counter(g.docente_id for g in grupos)
    botones = []
    for docente in Docente.objects.all():
        botones.append(
            {
                "obj": docente,
                "n_grupos": por_docente.get(docente.id_docente, 0),
                "elegido": docente.id_docente == id_elegido,
            }
        )
    # Primero quien más dicta; los que no tienen ninguno, al final.
    botones.sort(key=lambda b: (-b["n_grupos"], b["obj"].apellidos, b["obj"].nombres))
    return botones


@login_required
def cursos(request):
    """Página principal: un panel por cada grupo del docente."""
    todos_los_grupos = grupos_en_cache(request)
    grupos = list(todos_los_grupos)

    # Filtro por docente: solo tiene sentido para quien ve varios docentes.
    docente_elegido = None
    if request.user.es_admin and request.GET.get("docente"):
        docente_elegido = docente_por_id(request.GET["docente"])
        if docente_elegido is None:
            # Antes se ignoraba el filtro sin decir nada y salian TODOS los
            # cursos: la pantalla contradecia a la URL. Mejor avisar y
            # devolver a la lista completa, que es lo que se va a ver.
            messages.error(
                request,
                "Ese docente ya no existe; te muestro todos los grupos.",
            )
            return redirect("cursos")
        grupos = [g for g in grupos if g.docente_id == docente_elegido.id_docente]

    stats = estadisticas_de_grupos([g.id_grupo for g in grupos])

    tarjetas = []
    total_alumnos = 0
    porcentajes = []
    for grupo in grupos:
        datos = stats[grupo.id_grupo]
        total_alumnos += datos["total_alumnos"]
        if datos["porcentaje_promedio"] is not None:
            porcentajes.append(datos["porcentaje_promedio"])
        tarjetas.append(
            {
                "grupo": grupo,
                "semaforo": clasificar(datos["porcentaje_promedio"]),
                # El administrador ve todos los cursos, pero solo el titular
                # puede llamar asistencia en el suyo.
                "es_titular": es_docente_titular(request.user, grupo),
                **datos,
            }
        )

    promedio = round(sum(porcentajes) / len(porcentajes), 1) if porcentajes else None

    return render(
        request,
        "cursos.html",
        {
            "titulo": "Mis cursos",
            "seccion": "cursos",
            "panel_docentes": (
                panel_de_docentes(
                    todos_los_grupos,
                    docente_elegido.id_docente if docente_elegido else None,
                )
                if request.user.es_admin
                else []
            ),
            "docente_elegido": docente_elegido,
            "total_de_todos": len(todos_los_grupos),
            "tarjetas": tarjetas,
            "total_grupos": len(grupos),
            "total_alumnos": total_alumnos,
            "promedio_general": promedio,
        },
    )


@login_required
def matriculados(request, id_grupo):
    """Lista de matriculados tal como sale en el reporte oficial."""
    grupo = obtener_grupo(request.user, id_grupo)
    filas = (
        VistaListaMatriculados.objects.filter(id_grupo=id_grupo)
        .order_by("estudiante")
        .values("id_matricula", "codigo_estudiante", "estudiante", "intento", "estado_matricula")
    )
    alumnos = [
        {
            "numero": indice,
            "id_matricula": fila["id_matricula"],
            "codigo": fila["codigo_estudiante"],
            "nombre": fila["estudiante"],
            "intento": fila["intento"],
            "estado_matricula": fila["estado_matricula"],
        }
        for indice, fila in enumerate(filas, start=1)
    ]
    return render(
        request,
        "matriculados.html",
        {
            "titulo": "Estudiantes matriculados",
            "seccion": "reporte",
            "grupo": grupo,
            "es_titular": es_docente_titular(request.user, grupo),
            "alumnos": alumnos,
        },
    )
