"""
Alta, edición y baja de cursos.

Un «curso» en la pantalla es la combinación curso + grupo: el curso guarda
el código, el nombre, los créditos y el semestre; el grupo guarda la
sección, el periodo y el docente. Se administran juntos para no tener que
pensar en dos tablas.

Todo este módulo es exclusivo del ADMIN (`@solo_admin`): el docente
consulta sus cursos y llama asistencia, pero no los crea ni los borra.
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from asistencia.models import Asistencia, EstadoAsistencia, SesionClase
from cuentas.models import docente_por_id
from cuentas.seguridad import Evento, anotar

from .acceso import obtener_grupo, solo_admin
from .models import (
    Curso,
    EscuelaProfesional,
    Estudiante,
    Grupo,
    Matricula,
    PeriodoAcademico,
)


def _limpiar(valor, mayusculas=False):
    valor = (valor or "").strip()
    return valor.upper() if mayusculas else valor


def _creditos(valor):
    try:
        numero = Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, TypeError):
        return None
    if numero <= 0 or numero >= 100:
        return None
    return numero.quantize(Decimal("0.01"))


def _fecha(valor):
    """Fecha de un `<input type="date">`; None si viene vacía o mal escrita."""
    valor = (valor or "").strip()
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def _semestre(valor):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    return numero if 1 <= numero <= 10 else None


def _docente_destino(request):
    """El administrador elige a qué docente se asigna el curso."""
    return docente_por_id(request.POST.get("id_docente"), solo_activos=True)


@login_required
@solo_admin
@require_POST
def crear_curso(request):
    """Crea el curso y su primer grupo, ya asignado a un docente."""
    codigo = _limpiar(request.POST.get("codigo"), mayusculas=True)
    nombre = _limpiar(request.POST.get("nombre"), mayusculas=True)
    grupo_nombre = _limpiar(request.POST.get("grupo"), mayusculas=True) or "GRUPO A"
    creditos = _creditos(request.POST.get("creditos"))
    semestre = _semestre(request.POST.get("semestre"))

    if not codigo or not nombre:
        messages.error(request, "El código y el nombre del curso son obligatorios.")
        return redirect("cursos")
    if creditos is None:
        messages.error(request, "Los créditos deben ser un número mayor que cero (por ejemplo 2.00).")
        return redirect("cursos")
    if semestre is None:
        messages.error(request, "El semestre debe ser un número del 1 al 10.")
        return redirect("cursos")

    docente = _docente_destino(request)
    if docente is None:
        messages.error(request, "Selecciona un docente válido para el curso.")
        return redirect("cursos")

    escuela = EscuelaProfesional.objects.filter(pk=request.POST.get("id_escuela")).first()
    if escuela is None:
        escuela = EscuelaProfesional.objects.order_by("id_escuela").first()
    if escuela is None:
        messages.error(request, "No hay ninguna escuela profesional registrada en la base.")
        return redirect("cursos")

    periodo = PeriodoAcademico.objects.filter(pk=request.POST.get("id_periodo")).first()
    if periodo is None:
        periodo = (
            PeriodoAcademico.objects.filter(activo=True).order_by("-codigo").first()
            or PeriodoAcademico.objects.order_by("-codigo").first()
        )
    if periodo is None:
        messages.error(request, "No hay ningún periodo académico registrado en la base.")
        return redirect("cursos")

    try:
        with transaction.atomic():
            curso = Curso.objects.filter(escuela=escuela, codigo=codigo).first()
            if curso is None:
                curso = Curso.objects.create(
                    escuela=escuela, codigo=codigo, nombre=nombre,
                    creditos=creditos, semestre=semestre,
                )
            if Grupo.objects.filter(curso=curso, periodo=periodo, nombre=grupo_nombre).exists():
                messages.error(
                    request,
                    f"Ya existe «{codigo} · {grupo_nombre}» en el periodo {periodo.codigo}.",
                )
                return redirect("cursos")

            grupo = Grupo.objects.create(
                curso=curso, periodo=periodo, docente=docente, nombre=grupo_nombre
            )
    except IntegrityError:
        messages.error(request, "No se pudo crear el curso: ya existe uno con ese código.")
        return redirect("cursos")

    anotar(
        request,
        Evento.CURSO_CREADO,
        detalle=f"{codigo} · {grupo_nombre} → {docente.nombre_completo}",
    )
    messages.success(
        request,
        f"Curso «{codigo} - {nombre}» ({grupo_nombre}) creado. "
        "Ahora matricula a los estudiantes para poder llamar asistencia.",
    )
    return redirect("matriculados", id_grupo=grupo.id_grupo)


@login_required
@solo_admin
@require_POST
def editar_curso(request, id_grupo):
    """Cambia el nombre, el código, los créditos, el semestre y la sección."""
    grupo = obtener_grupo(request.user, id_grupo)

    nombre = _limpiar(request.POST.get("nombre"), mayusculas=True)
    codigo = _limpiar(request.POST.get("codigo"), mayusculas=True)
    grupo_nombre = _limpiar(request.POST.get("grupo"), mayusculas=True)
    creditos = _creditos(request.POST.get("creditos"))
    semestre = _semestre(request.POST.get("semestre"))

    if not nombre or not codigo or not grupo_nombre:
        messages.error(request, "El código, el nombre del curso y la sección son obligatorios.")
        return redirect("cursos")
    if creditos is None:
        messages.error(request, "Los créditos deben ser un número mayor que cero.")
        return redirect("cursos")
    if semestre is None:
        messages.error(request, "El semestre debe ser un número del 1 al 10.")
        return redirect("cursos")

    duplicado = (
        Curso.objects.filter(escuela_id=grupo.curso.escuela_id, codigo=codigo)
        .exclude(pk=grupo.curso_id)
        .exists()
    )
    if duplicado:
        messages.error(request, f"Ya hay otro curso con el código «{codigo}» en esa escuela.")
        return redirect("cursos")

    choque = (
        Grupo.objects.filter(curso_id=grupo.curso_id, periodo_id=grupo.periodo_id, nombre=grupo_nombre)
        .exclude(pk=grupo.pk)
        .exists()
    )
    if choque:
        messages.error(request, f"Ya existe la sección «{grupo_nombre}» en este curso y periodo.")
        return redirect("cursos")

    with transaction.atomic():
        curso = grupo.curso
        curso.codigo = codigo
        curso.nombre = nombre
        curso.creditos = creditos
        curso.semestre = semestre
        curso.save(update_fields=["codigo", "nombre", "creditos", "semestre"])

        grupo.nombre = grupo_nombre
        grupo.save(update_fields=["nombre"])

    anotar(request, Evento.CURSO_EDITADO, detalle=f"{codigo} · {grupo_nombre}")
    messages.success(request, f"Curso «{codigo} - {nombre}» actualizado.")
    return redirect("cursos")


@login_required
@solo_admin
@require_POST
def eliminar_curso(request, id_grupo):
    """
    Elimina el grupo con todo lo que cuelga de el.

    Se lleva por delante las clases dictadas y su asistencia, que son el
    registro oficial del curso, asi que la pantalla avisa del numero exacto
    antes de confirmar. El orden importa: las claves foraneas de la base no
    dejan borrar una matricula con asistencia, ni un grupo con sesiones.
    """
    grupo = obtener_grupo(request.user, id_grupo)

    etiqueta = f"{grupo.curso.codigo} · {grupo.nombre}"
    id_curso = grupo.curso_id
    sesiones = SesionClase.objects.filter(grupo_id=grupo.pk)
    n_clases = sesiones.count()
    n_matriculas = Matricula.objects.filter(grupo_id=grupo.pk).count()

    with transaction.atomic():
        # Primero la asistencia, que cuelga de las sesiones y de las
        # matriculas; despues las sesiones; luego las matriculas.
        Asistencia.objects.filter(sesion__grupo_id=grupo.pk).delete()
        sesiones.delete()
        Matricula.objects.filter(grupo_id=grupo.pk).delete()
        grupo.delete()
        # El curso solo existe para sus grupos: si se queda sin ninguno, sobra.
        if not Grupo.objects.filter(curso_id=id_curso).exists():
            Curso.objects.filter(pk=id_curso).delete()

    anotar(
        request,
        Evento.CURSO_ELIMINADO,
        detalle=f"{etiqueta} ({n_matriculas} matrículas, {n_clases} clases)",
    )
    detalle = f"{n_matriculas} matrícula{'s' if n_matriculas != 1 else ''}"
    if n_clases:
        detalle += f" y {n_clases} clase{'s' if n_clases != 1 else ''} con su asistencia"
    messages.success(request, f"Curso «{etiqueta}» eliminado, junto con {detalle}.")
    return redirect("cursos")


@login_required
@solo_admin
@require_POST
def eliminar_sesion(request, id_sesion):
    """
    Elimina una clase con toda su asistencia.

    Es para las clases abiertas por error: una de prueba, la misma clase
    iniciada dos veces, el curso equivocado. Vale tambien para una cerrada,
    porque el docente pudo cerrarla sin notar el error. Como una cerrada es
    parte del registro oficial, el apunte de seguridad guarda lo necesario
    para saber despues que se borro: curso, fecha, hora, docente, estado y
    el recuento de presentes y faltas.

    No hay trigger que lo impida: los de `asistencia` vigilan INSERT y
    UPDATE, no DELETE.
    """
    sesion = get_object_or_404(
        SesionClase.objects.select_related("grupo__curso", "docente"), pk=id_sesion
    )
    id_grupo = sesion.grupo_id
    marcas = Asistencia.objects.filter(sesion_id=sesion.pk)
    total = marcas.count()
    presentes = marcas.filter(estado=EstadoAsistencia.PRESENTE).count()

    cuando = f"{sesion.fecha:%d/%m/%Y} {sesion.hora_inicio:%H:%M}"
    etiqueta = f"{sesion.grupo.curso.codigo} · {sesion.grupo.nombre}"

    with transaction.atomic():
        # Primero la asistencia, que cuelga de la sesion; igual que al
        # eliminar un curso, sin fiarse del ON DELETE CASCADE.
        marcas.delete()
        sesion.delete()

    anotar(
        request,
        Evento.CLASE_ELIMINADA,
        detalle=(
            f"{etiqueta}: clase del {cuando} de {sesion.docente.nombre_completo} "
            f"({sesion.get_estado_display().lower()}, {presentes} P / {total - presentes} F)"
        ),
    )
    messages.success(
        request,
        f"Clase del {cuando} eliminada, junto con la asistencia de {total} "
        f"alumno{'s' if total != 1 else ''}.",
    )
    return redirect("historial", id_grupo=id_grupo)




@login_required
@solo_admin
@require_POST
def matricular(request, id_grupo):
    """Matricula estudiantes existentes en el grupo (por código, uno por línea)."""
    grupo = obtener_grupo(request.user, id_grupo)

    codigos = [c.strip() for c in (request.POST.get("codigos") or "").replace(",", "\n").split("\n")]
    codigos = [c for c in codigos if c]
    if not codigos:
        messages.error(request, "Escribe al menos un código de estudiante.")
        return redirect("matriculados", id_grupo=id_grupo)

    encontrados = {e.codigo: e for e in Estudiante.objects.filter(codigo__in=codigos)}
    ya_estaban = set(
        Matricula.objects.filter(grupo_id=id_grupo).values_list("estudiante__codigo", flat=True)
    )

    # USE_TZ=False: `localdate()` no sirve con fechas naive, `now().date()` sí.
    hoy = timezone.now().date()
    nuevos, repetidos, faltantes = 0, 0, []
    for codigo in codigos:
        estudiante = encontrados.get(codigo)
        if estudiante is None:
            faltantes.append(codigo)
            continue
        if codigo in ya_estaban:
            repetidos += 1
            continue
        Matricula.objects.create(
            grupo=grupo,
            estudiante=estudiante,
            intento=1,
            estado=Matricula.Estado.ACTIVA,
            fecha_matricula=hoy,
        )
        ya_estaban.add(codigo)
        nuevos += 1

    if nuevos:
        anotar(
            request,
            Evento.ESTUDIANTES,
            detalle=f"{nuevos} matriculados en {grupo.curso.codigo} · {grupo.nombre}",
        )
        messages.success(request, f"{nuevos} estudiante(s) matriculado(s).")
    if repetidos:
        messages.info(request, f"{repetidos} ya estaban matriculados.")
    if faltantes:
        messages.error(
            request,
            "No existen estudiantes con estos códigos: " + ", ".join(faltantes[:10])
            + (" …" if len(faltantes) > 10 else ""),
        )
    return redirect("matriculados", id_grupo=id_grupo)


@login_required
@solo_admin
@require_POST
def quitar_matricula(request, id_grupo, id_matricula):
    """Quita a un estudiante del grupo, si aún no tiene asistencia registrada."""
    obtener_grupo(request.user, id_grupo)
    matricula = get_object_or_404(Matricula, pk=id_matricula, grupo_id=id_grupo)

    if matricula.asistencias.exists():
        messages.error(
            request,
            "Ese estudiante ya tiene asistencia registrada; no se puede quitar del curso.",
        )
        return redirect("matriculados", id_grupo=id_grupo)

    nombre = matricula.estudiante.nombre_completo
    matricula.delete()
    anotar(request, Evento.MATRICULA_QUITADA, detalle=nombre)
    messages.success(request, f"{nombre} fue retirado del curso.")
    return redirect("matriculados", id_grupo=id_grupo)


# ---------------------------------------------------------------------
# Alta e importación de estudiantes
# ---------------------------------------------------------------------
# Al pegar desde Excel las columnas llegan separadas por tabulador; escritas
# a mano, por punto y coma. Se aceptan ambas (y la barra vertical).
SEPARADORES = re.compile(r"[;\t|]")

# Largos de las columnas de la tabla `estudiante`. Comprobarlos aquí da un
# mensaje con el número de línea en vez del error 1406 de MySQL.
LARGOS_ESTUDIANTE = {
    "codigo": 10,
    "apellido_paterno": 60,
    "apellido_materno": 60,
    "nombres": 100,
    "email": 120,
}


def leer_lista_de_estudiantes(texto):
    """
    Convierte el bloque pegado en `(fichas, errores)`.

    Cada línea es `CODIGO;APELLIDO PATERNO;APELLIDO MATERNO;NOMBRES[;CORREO]`.
    Los errores salen con su número de línea para poder corregir el pegado sin
    adivinar dónde estaba el fallo; las líneas correctas del mismo bloque se
    procesan igual.
    """
    fichas, errores, vistos = [], [], set()

    for numero, linea in enumerate(texto.splitlines(), start=1):
        if not linea.strip():
            continue

        partes = [parte.strip() for parte in SEPARADORES.split(linea)]
        if len(partes) < 4:
            errores.append(
                f"Línea {numero}: faltan datos. Se esperan código, apellido "
                "paterno, apellido materno y nombres separados por «;»."
            )
            continue

        codigo, paterno, materno, nombres = partes[:4]
        email = partes[4] if len(partes) > 4 else ""

        if not codigo:
            errores.append(f"Línea {numero}: el código está vacío.")
            continue
        if not paterno or not nombres:
            errores.append(
                f"Línea {numero} ({codigo}): el apellido paterno y los nombres "
                "son obligatorios."
            )
            continue
        if codigo in vistos:
            errores.append(
                f"Línea {numero}: el código {codigo} está repetido en la lista."
            )
            continue

        ficha = {
            "codigo": codigo,
            "apellido_paterno": paterno.upper(),
            "apellido_materno": materno.upper(),
            "nombres": nombres.upper(),
            "email": email or None,
        }
        largos = [
            campo
            for campo, tope in LARGOS_ESTUDIANTE.items()
            if ficha[campo] and len(ficha[campo]) > tope
        ]
        if largos:
            errores.append(
                f"Línea {numero} ({codigo}): {', '.join(largos)} supera el largo "
                "permitido."
            )
            continue

        vistos.add(codigo)
        fichas.append(ficha)

    return fichas, errores


@login_required
@solo_admin
@require_POST
def importar_estudiantes(request, id_grupo):
    """
    Registra a los estudiantes que aún no existan y los matricula en el grupo.

    Hasta ahora solo se podía matricular a quien ya estuviera en la tabla
    `estudiante`, así que dar de alta a un alumno nuevo obligaba a entrar a
    phpMyAdmin. Aquí se pega la lista del aula y el sistema crea lo que falte,
    asignando los alumnos a la escuela del curso.
    """
    grupo = obtener_grupo(request.user, id_grupo)

    fichas, errores = leer_lista_de_estudiantes(request.POST.get("lista") or "")
    if not fichas and not errores:
        messages.error(request, "Pega al menos una línea con los datos del estudiante.")
        return redirect("matriculados", id_grupo=id_grupo)

    hoy = timezone.now().date()
    existentes = {
        e.codigo: e
        for e in Estudiante.objects.filter(codigo__in=[f["codigo"] for f in fichas])
    }
    ya_matriculados = set(
        Matricula.objects.filter(grupo_id=id_grupo).values_list(
            "estudiante__codigo", flat=True
        )
    )

    creados = nuevas_matriculas = repetidos = 0
    try:
        # O entra la lista entera o no entra nada: así un fallo a mitad no deja
        # estudiantes creados pero sin matricular.
        with transaction.atomic():
            for ficha in fichas:
                estudiante = existentes.get(ficha["codigo"])
                if estudiante is None:
                    estudiante = Estudiante.objects.create(
                        escuela=grupo.curso.escuela, activo=True, **ficha
                    )
                    creados += 1
                # Si el código ya existía se respeta la ficha de la base: esta
                # pantalla matricula, no corrige datos de alumnos.

                if ficha["codigo"] in ya_matriculados:
                    repetidos += 1
                    continue

                Matricula.objects.create(
                    grupo=grupo,
                    estudiante=estudiante,
                    intento=1,
                    estado=Matricula.Estado.ACTIVA,
                    fecha_matricula=hoy,
                )
                ya_matriculados.add(ficha["codigo"])
                nuevas_matriculas += 1
    except IntegrityError:
        messages.error(
            request,
            "No se pudo guardar la lista: algún código ya está registrado con "
            "otros datos. No se registró ningún cambio.",
        )
        return redirect("matriculados", id_grupo=id_grupo)

    if creados or nuevas_matriculas:
        anotar(
            request,
            Evento.ESTUDIANTES,
            detalle=(
                f"{creados} nuevos, {nuevas_matriculas} matriculados en "
                f"{grupo.curso.codigo} · {grupo.nombre}"
            ),
        )
    if creados:
        messages.success(request, f"{creados} estudiante(s) registrado(s) por primera vez.")
    if nuevas_matriculas:
        messages.success(
            request,
            f"{nuevas_matriculas} matriculado(s) en {grupo.curso.codigo} · {grupo.nombre}.",
        )
    if repetidos:
        messages.info(request, f"{repetidos} ya estaban matriculados.")
    for error in errores[:10]:
        messages.error(request, error)
    if len(errores) > 10:
        messages.error(request, f"… y {len(errores) - 10} línea(s) más con problemas.")

    return redirect("matriculados", id_grupo=id_grupo)


# ---------------------------------------------------------------------
# Periodos académicos
# ---------------------------------------------------------------------
@login_required
@solo_admin
@require_POST
def crear_periodo(request):
    """Alta de un periodo (2026-I, 2026-II…) para poder abrir cursos en él."""
    codigo = _limpiar(request.POST.get("codigo"), mayusculas=True)
    if not codigo:
        messages.error(request, "El código del periodo es obligatorio (por ejemplo 2026-II).")
        return redirect("admin-panel")
    if len(codigo) > 10:
        messages.error(request, "El código del periodo admite como máximo 10 caracteres.")
        return redirect("admin-panel")
    if PeriodoAcademico.objects.filter(codigo=codigo).exists():
        messages.error(request, f"El periodo «{codigo}» ya está registrado.")
        return redirect("admin-panel")

    inicio = _fecha(request.POST.get("fecha_inicio"))
    fin = _fecha(request.POST.get("fecha_fin"))
    if inicio and fin and fin < inicio:
        messages.error(request, "La fecha de fin no puede ser anterior a la de inicio.")
        return redirect("admin-panel")

    PeriodoAcademico.objects.create(
        codigo=codigo,
        fecha_inicio=inicio,
        fecha_fin=fin,
        activo=bool(request.POST.get("activo")),
    )
    anotar(request, Evento.PERIODO_CREADO, detalle=codigo)
    messages.success(request, f"Periodo «{codigo}» creado.")
    return redirect("admin-panel")
