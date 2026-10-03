"""Llamado de asistencia: abrir la clase, marcar, cerrar y consultar el historial."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academico.acceso import docente_titular, es_docente_titular, obtener_grupo
from academico.models import Matricula

from .errores import ErrorDeNegocio
from .models import Asistencia, EstadoAsistencia, SesionClase
from .services import cerrar_sesion_clase, iniciar_sesion_clase, marcar_asistencia_en_lote

# Orden en que se muestran los botones P / T / F / J.
ESTADOS = [
    {"valor": "PRESENTE", "letra": "P", "nombre": "Presente", "clase": "presente"},
    {"valor": "FALTA", "letra": "F", "nombre": "Falta", "clase": "falta"},
]


def resumen_de_sesiones(ids_sesion):
    """Conteo por estado para un conjunto de sesiones, en una sola consulta."""
    base = {
        id_sesion: {
            "total": 0, "presentes": 0,
            "faltas": 0, "porcentaje": None,
        }
        for id_sesion in ids_sesion
    }
    if not ids_sesion:
        return base

    filas = (
        Asistencia.objects.filter(sesion_id__in=ids_sesion)
        .values("sesion_id")
        .annotate(
            total=Count("id_asistencia"),
            presentes=Count("id_asistencia", filter=Q(estado=EstadoAsistencia.PRESENTE)),
            faltas=Count("id_asistencia", filter=Q(estado=EstadoAsistencia.FALTA)),
        )
    )
    for fila in filas:
        total = fila["total"] or 0
        # Con dos estados, asistir es estar presente.
        asistio = fila["presentes"]
        base[fila["sesion_id"]] = {
            "total": total,
            "presentes": fila["presentes"],
            "faltas": fila["faltas"],
            "porcentaje": round(100 * asistio / total, 2) if total else None,
        }
    return base


def obtener_sesion(usuario, id_sesion):
    """Devuelve la sesión validando que el usuario tenga acceso a su grupo."""
    sesion = (
        SesionClase.objects.select_related(
            "grupo", "grupo__curso", "grupo__curso__escuela",
            "grupo__curso__escuela__facultad", "grupo__periodo", "grupo__docente", "docente",
        )
        .filter(pk=id_sesion)
        .first()
    )
    if sesion is None:
        raise Http404("La sesión de clase no existe.")
    if not usuario.es_admin:
        ficha = usuario.docente
        if ficha is None or sesion.grupo.docente_id != ficha.id_docente:
            raise PermissionDenied("No tienes asignado el grupo de esta sesión.")
    return sesion


def alumnos_de_sesion(id_sesion):
    """Alumnos de la sesión con su estado actual, en el orden del PDF oficial."""
    filas = (
        Asistencia.objects.filter(sesion_id=id_sesion)
        .select_related("matricula__estudiante")
        .order_by(
            "matricula__estudiante__apellido_paterno",
            "matricula__estudiante__apellido_materno",
            "matricula__estudiante__nombres",
        )
    )
    return [
        {
            "numero": numero,
            "id_matricula": marca.matricula_id,
            "codigo": marca.matricula.estudiante.codigo,
            "nombre": marca.matricula.estudiante.nombre_completo,
            "estado": marca.estado,
            "letra": marca.letra,
            "observacion": marca.observacion or "",
        }
        for numero, marca in enumerate(filas, start=1)
    ]


# ---------------------------------------------------------------------
# Abrir la clase
# ---------------------------------------------------------------------
@login_required
def llamar_asistencia(request, id_grupo):
    """Retoma la clase abierta o muestra el formulario para iniciar una nueva."""
    grupo = obtener_grupo(request.user, id_grupo)
    # Solo el titular abre clase. El administrador llega hasta aquí porque ve
    # todos los grupos, pero se le manda al historial, que es lo suyo.
    if not es_docente_titular(request.user, grupo):
        messages.info(
            request,
            f"Solo {grupo.docente.nombre_completo} puede llamar asistencia en "
            f"«{grupo.curso.codigo} · {grupo.nombre}». Aquí tienes el historial "
            "de clases.",
        )
        return redirect("historial", id_grupo=id_grupo)

    abierta = (
        SesionClase.objects.filter(grupo_id=id_grupo, estado=SesionClase.Estado.ABIERTA)
        .order_by("-fecha", "-hora_inicio")
        .first()
    )
    # Un grupo solo puede tener una clase abierta a la vez. La comprobación
    # corre también en POST: si no, un formulario reenviado (o dos pestañas
    # abiertas) crearía una segunda sesión y la primera quedaría huérfana.
    if abierta:
        if request.method == "POST":
            messages.info(
                request, "Ya había una clase abierta en este curso; se retomó esa."
            )
        return redirect("sesion", id_sesion=abierta.id_sesion)

    ahora = timezone.now()

    if request.method == "POST":
        fecha = request.POST.get("fecha") or ahora.date().isoformat()
        hora = request.POST.get("hora_inicio") or ahora.strftime("%H:%M")
        tema = (request.POST.get("tema") or "").strip() or None

        # La clase se firma a nombre de quien la dicta.
        ficha = docente_titular(request.user, grupo)

        try:
            id_sesion = iniciar_sesion_clase(
                id_grupo=grupo.id_grupo, id_docente=ficha.id_docente,
                fecha=fecha, hora_inicio=hora, tema=tema,
            )
        except ErrorDeNegocio as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                "Clase iniciada. Todos los alumnos empiezan marcados como Falta.",
            )
            return redirect("sesion", id_sesion=id_sesion)

    return render(
        request,
        "iniciar_clase.html",
        {
            "titulo": "Iniciar clase",
            "seccion": "asistencia",
            "grupo": grupo,
            # A esta pantalla solo llega el titular (arriba se comprueba).
            "es_titular": True,
            "hoy": ahora.date().isoformat(),
            "hora_actual": ahora.strftime("%H:%M"),
            "total_alumnos": grupo.matriculas.filter(
                estado=Matricula.Estado.ACTIVA
            ).count(),
        },
    )


# ---------------------------------------------------------------------
# Marcar asistencia
# ---------------------------------------------------------------------
@login_required
def sesion_detalle(request, id_sesion):
    """Lista de alumnos con sus botones P / T / F / J. El POST guarda todo."""
    sesion = obtener_sesion(request.user, id_sesion)
    # El administrador puede mirar la lista, pero no tocarla.
    es_titular = es_docente_titular(request.user, sesion.grupo)

    if request.method == "POST":
        if not es_titular:
            docente_titular(request.user, sesion.grupo)  # corta con 403
        if not sesion.esta_abierta:
            messages.error(request, "La sesión está cerrada; no se puede modificar.")
            return redirect("sesion", id_sesion=id_sesion)

        actuales = {a["id_matricula"]: a for a in alumnos_de_sesion(id_sesion)}
        cambios = []
        for id_matricula, alumno in actuales.items():
            estado = request.POST.get(f"estado_{id_matricula}")
            observacion = (request.POST.get(f"obs_{id_matricula}") or "").strip() or None
            if estado is None:
                continue
            # Solo se llama al procedimiento para lo que realmente cambió.
            if estado != alumno["estado"] or observacion != (alumno["observacion"] or None):
                cambios.append(
                    {"id_matricula": id_matricula, "estado": estado, "observacion": observacion}
                )

        tema = (request.POST.get("tema") or "").strip() or None
        cambio_el_tema = tema != sesion.tema

        guardado = True
        if cambios:
            try:
                marcar_asistencia_en_lote(id_sesion, cambios)
            except ErrorDeNegocio as exc:
                messages.error(request, str(exc))
                guardado = False
            else:
                messages.success(request, f"Asistencia guardada ({len(cambios)} cambios).")

        # El tema se graba después de las marcas y solo si estas no fallaron:
        # así un guardado a medias no deja el tema nuevo con la lista vieja.
        if guardado and cambio_el_tema:
            sesion.tema = tema
            sesion.save(update_fields=["tema"])

        if guardado and not cambios and not cambio_el_tema:
            messages.info(request, "No había cambios que guardar.")

        if guardado and request.POST.get("accion") == "guardar_y_cerrar":
            try:
                cerrar_sesion_clase(id_sesion)
            except ErrorDeNegocio as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    "Clase cerrada. La asistencia quedó registrada y ya no se puede modificar.",
                )
        return redirect("sesion", id_sesion=id_sesion)

    alumnos = alumnos_de_sesion(id_sesion)
    return render(
        request,
        "asistencia.html",
        {
            "titulo": "Llamar asistencia",
            "seccion": "asistencia",
            "sesion": sesion,
            "grupo": sesion.grupo,
            "alumnos": alumnos,
            "estados": ESTADOS,
            # Los contadores P/T/F/J de esta pantalla los calcula el navegador
            # sobre la marcha; no hace falta traerlos también de la base.
            "solo_lectura": not (sesion.esta_abierta and es_titular),
            "es_titular": es_titular,
        },
    )


@login_required
@require_POST
def cerrar_sesion_vista(request, id_sesion):
    sesion = obtener_sesion(request.user, id_sesion)
    docente_titular(request.user, sesion.grupo)
    try:
        cerrar_sesion_clase(id_sesion)
    except ErrorDeNegocio as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request, "Clase cerrada. La asistencia quedó registrada y ya no se puede modificar."
        )
    return redirect("sesion", id_sesion=sesion.id_sesion)


# ---------------------------------------------------------------------
# Historial
# ---------------------------------------------------------------------
@login_required
def historial(request, id_grupo):
    grupo = obtener_grupo(request.user, id_grupo)
    sesiones = list(
        SesionClase.objects.select_related("docente")
        .filter(grupo_id=id_grupo)
        .order_by("-fecha", "-hora_inicio")
    )
    resumenes = resumen_de_sesiones([s.id_sesion for s in sesiones])

    filas = [{"sesion": s, "resumen": resumenes[s.id_sesion]} for s in sesiones]

    return render(
        request,
        "historial.html",
        {
            "titulo": "Historial de clases",
            "seccion": "historial",
            "grupo": grupo,
            "filas": filas,
            "es_titular": es_docente_titular(request.user, grupo),
            "cerradas": sum(1 for s in sesiones if s.estado == "CERRADA"),
            "abiertas": sum(1 for s in sesiones if s.estado == "ABIERTA"),
        },
    )
