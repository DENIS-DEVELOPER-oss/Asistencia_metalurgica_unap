"""
Armado de los datos que alimentan la pantalla de reporte, el Excel y el PDF.

Una sola función construye la estructura para los tres destinos, de modo que
los tres muestren exactamente lo mismo.
"""
from datetime import datetime

from django.conf import settings

from academico.models import Matricula
from asistencia.models import LETRA_ESTADO, Asistencia, SesionClase

from .models import VistaResumenAsistencia


def fecha_de_emision():
    """Momento en que se genera el reporte; se imprime en los tres formatos."""
    return datetime.now()


def _a_float(valor):
    return float(valor) if valor is not None else None


def clasificar(porcentaje_asistencia):
    """Color del semáforo según el porcentaje de asistencia."""
    if porcentaje_asistencia is None:
        return "sin_datos"
    if porcentaje_asistencia >= settings.SEMAFORO_VERDE:
        return "verde"
    if porcentaje_asistencia >= settings.SEMAFORO_AMBAR:
        return "ambar"
    return "rojo"


def cabecera_de_grupo(grupo):
    """Encabezado del reporte oficial."""
    return {
        "id_grupo": grupo.id_grupo,
        "universidad": "UNIVERSIDAD NACIONAL DEL ALTIPLANO PUNO",
        "facultad": grupo.curso.escuela.facultad.nombre,
        "escuela": grupo.curso.escuela.nombre,
        "codigo_curso": grupo.curso.codigo,
        "curso": grupo.curso.nombre,
        "creditos": f"{grupo.curso.creditos:.2f}",
        "semestre": grupo.curso.semestre,
        "semestre_texto": grupo.curso.semestre_texto,
        "grupo": grupo.nombre,
        "periodo": grupo.periodo.codigo,
        "docente": grupo.docente.nombre_completo,
    }


def construir_reporte(grupo):
    """
    Devuelve un diccionario con:
      - cabecera: datos del curso
      - sesiones: lista de clases dictadas (columnas del reporte)
      - alumnos: una fila por estudiante con la letra de cada fecha y totales
      - umbral / semaforo: parámetros de negocio aplicados
    """
    id_grupo = grupo.id_grupo
    umbral = float(settings.UMBRAL_INHABILITACION)

    sesiones = list(
        SesionClase.objects.filter(grupo_id=id_grupo).order_by("fecha", "hora_inicio")
    )
    columnas = [
        {
            "id_sesion": sesion.id_sesion,
            "fecha": sesion.fecha,
            "hora_inicio": sesion.hora_inicio,
            "tema": sesion.tema,
            "estado": sesion.estado,
            "etiqueta": sesion.fecha.strftime("%d/%m"),
        }
        for sesion in sesiones
    ]

    # Matriz alumno (código) -> sesión -> letra
    matriz = {}
    marcas = Asistencia.objects.filter(sesion__grupo_id=id_grupo).values(
        "sesion_id", "estado", "matricula__estudiante__codigo"
    )
    for marca in marcas:
        codigo = marca["matricula__estudiante__codigo"]
        matriz.setdefault(codigo, {})[marca["sesion_id"]] = LETRA_ESTADO.get(
            marca["estado"], "-"
        )

    # `v_resumen_asistencia` incluye también las matrículas RETIRADA, que no
    # se evalúan: aparecerían en el reporte oficial con cero clases. La
    # pantalla «Matriculados» sí las sigue mostrando, con su estado.
    codigos_activos = set(
        Matricula.objects.filter(
            grupo_id=id_grupo, estado=Matricula.Estado.ACTIVA
        ).values_list("estudiante__codigo", flat=True)
    )
    resumen = [
        fila
        for fila in VistaResumenAsistencia.objects.filter(id_grupo=id_grupo).order_by(
            "estudiante"
        )
        if fila.codigo_estudiante in codigos_activos
    ]

    alumnos = []
    for numero, fila in enumerate(resumen, start=1):
        porcentaje = _a_float(fila.porcentaje_asistencia)
        total = fila.total_sesiones or 0
        faltas = fila.faltas or 0
        porcentaje_faltas = round(100 * faltas / total, 2) if total else None
        en_riesgo = porcentaje_faltas is not None and porcentaje_faltas > umbral
        marcas_del_alumno = matriz.get(fila.codigo_estudiante, {})

        alumnos.append(
            {
                "numero": numero,
                "codigo": fila.codigo_estudiante,
                "nombre": fila.estudiante,
                "total_sesiones": total,
                "presentes": fila.presentes or 0,
                "faltas": faltas,
                "porcentaje_asistencia": porcentaje,
                "porcentaje_faltas": porcentaje_faltas,
                "en_riesgo": en_riesgo,
                "semaforo": clasificar(porcentaje),
                # `marcas` va indexada por sesión: el PDF parte las fechas en
                # bloques y necesita buscar por id. `celdas` es la misma
                # información ya alineada con `sesiones`, que es lo que la
                # plantilla puede recorrer.
                "marcas": marcas_del_alumno,
                "celdas": [
                    marcas_del_alumno.get(columna["id_sesion"], "")
                    for columna in columnas
                ],
            }
        )

    porcentajes = [a["porcentaje_asistencia"] for a in alumnos if a["porcentaje_asistencia"] is not None]
    promedio = round(sum(porcentajes) / len(porcentajes), 2) if porcentajes else None

    return {
        "cabecera": cabecera_de_grupo(grupo),
        "fecha_emision": fecha_de_emision(),
        "sesiones": columnas,
        "alumnos": alumnos,
        "total_alumnos": len(alumnos),
        "total_sesiones": len(columnas),
        "porcentaje_promedio": promedio,
        "total_en_riesgo": sum(1 for a in alumnos if a["en_riesgo"]),
        "umbral_inhabilitacion": umbral,
        "semaforo": {"verde": settings.SEMAFORO_VERDE, "ambar": settings.SEMAFORO_AMBAR},
    }


def datos_de_sesion(sesion):
    """Datos de una sola clase, para el PDF de lista de asistencia."""
    filas = (
        Asistencia.objects.filter(sesion_id=sesion.id_sesion)
        .select_related("matricula__estudiante")
        .order_by(
            "matricula__estudiante__apellido_paterno",
            "matricula__estudiante__apellido_materno",
            "matricula__estudiante__nombres",
        )
    )
    alumnos = []
    conteo = {"PRESENTE": 0, "FALTA": 0}
    for numero, marca in enumerate(filas, start=1):
        estudiante = marca.matricula.estudiante
        conteo[marca.estado] = conteo.get(marca.estado, 0) + 1
        alumnos.append(
            {
                "numero": numero,
                "codigo": estudiante.codigo,
                "nombre": estudiante.nombre_completo,
                "estado": marca.estado,
                "letra": marca.letra,
                "observacion": marca.observacion or "",
            }
        )

    total = len(alumnos)
    asistio = conteo["PRESENTE"]
    return {
        "cabecera": cabecera_de_grupo(sesion.grupo),
        "fecha_emision": fecha_de_emision(),
        "sesion": {
            "id_sesion": sesion.id_sesion,
            "fecha": sesion.fecha,
            "hora_inicio": sesion.hora_inicio,
            "hora_fin": sesion.hora_fin,
            "tema": sesion.tema or "",
            "estado": sesion.estado,
        },
        "alumnos": alumnos,
        "resumen": {
            "total": total,
            "presentes": conteo["PRESENTE"],
            "faltas": conteo["FALTA"],
            "porcentaje_asistencia": round(100 * asistio / total, 2) if total else None,
        },
    }
