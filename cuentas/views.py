"""Acceso al sistema y panel de administración."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from academico.acceso import grupos_en_cache, solo_admin
from academico.models import (
    ORDINALES_SEMESTRE,
    EscuelaProfesional,
    Grupo,
    Matricula,
    PeriodoAcademico,
)
from asistencia.models import SesionClase

# [(1, 'PRIMERO'), (2, 'SEGUNDO'), …] para el formulario de curso.
SEMESTRES = sorted(ORDINALES_SEMESTRE.items())

# Cuántas filas del registro de seguridad se pintan de una vez.
EVENTOS_EN_PANTALLA = 200

from .models import Docente, Usuario, docente_por_id
from .seguridad import (
    DIAS_QUE_SE_GUARDA,
    LIMITE_POR_USUARIO,
    VENTANA,
    Evento,
    EventoSeguridad,
    anotar,
    estado_del_acceso,
    ip_de,
)


# ---------------------------------------------------------------------
# Acceso
# ---------------------------------------------------------------------
def destino_tras_entrar(request):
    """
    URL del parámetro `next`, solo si apunta a este mismo sitio.

    Sin esta comprobación, un enlace como /login/?next=https://sitio-falso.com
    mandaría al docente fuera del sistema justo después de escribir su clave.
    """
    destino = request.POST.get("next") or request.GET.get("next") or ""
    if destino and url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return destino
    return None


def login_vista(request):
    """
    Entrada al sistema, con un límite de intentos seguidos.

    La contraseña inicial de un docente es su DNI, ocho dígitos: sin un
    límite, un programa los prueba todos en una tarde. Tras varios fallos
    la cuenta queda en espera unos minutos, lo que basta para que el
    tanteo deje de ser viable sin castigar a quien se equivocó al
    escribir.
    """
    if request.user.is_authenticated:
        return redirect(destino_tras_entrar(request) or "cursos")

    error = ""
    aviso = ""
    username = ""

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        ip = ip_de(request)

        bloqueado, minutos = estado_del_acceso(username, ip)

        if bloqueado:
            anotar(request, Evento.LOGIN_BLOQUEADO, usuario=username)
            error = _mensaje_de_espera(minutos)
        elif not username or not password:
            error = "Escribe tu usuario y tu contraseña."
        else:
            usuario = authenticate(request, username=username, password=password)
            if usuario is None:
                anotar(request, Evento.LOGIN_FALLIDO, usuario=username)
                error = "Usuario o contraseña incorrectos, o la cuenta está inactiva."
                # Si este fallo fue el que agotó los intentos, se avisa
                # aquí mismo. Enterarse recién al reintentar parecería que
                # el sistema se estropeó.
                ahora_bloqueado, minutos = estado_del_acceso(username, ip)
                if ahora_bloqueado:
                    error += " " + _mensaje_de_espera(minutos)
                else:
                    aviso = _intentos_que_quedan(username, ip)
            else:
                # `login()` renueva la sesión por dentro, así que lo que
                # hubiera quedado de una sesión anterior en esta PC no pasa.
                login(request, usuario)
                anotar(request, Evento.LOGIN_OK, usuario=usuario.username)
                messages.success(request, f"Bienvenido(a), {usuario.nombre_completo}")
                return redirect(destino_tras_entrar(request) or "cursos")

    return render(
        request,
        "login.html",
        {
            "error": error,
            "aviso": aviso,
            "username": username,
            "next": destino_tras_entrar(request) or "",
        },
    )


def _mensaje_de_espera(minutos):
    return (
        f"Demasiados intentos fallidos: el acceso queda en espera "
        f"{minutos} minuto{'s' if minutos != 1 else ''}. Si olvidaste tu "
        "contraseña, pídele al administrador que te asigne una nueva."
    )


def _intentos_que_quedan(username, ip):
    """
    Aviso de cuántos intentos faltan para el bloqueo, cuando ya quedan pocos.

    Solo se muestra al final, para que quien se equivocó una vez no se
    asuste y para no regalarle la cuenta exacta a quien esté tanteando.
    """
    fallos = EventoSeguridad.objects.filter(
        tipo=Evento.LOGIN_FALLIDO, usuario=username, momento__gte=timezone.now() - VENTANA
    ).count()
    faltan = LIMITE_POR_USUARIO - fallos
    if 0 < faltan <= 2:
        return (
            f"Te queda{'n' if faltan != 1 else ''} {faltan} "
            f"intento{'s' if faltan != 1 else ''} antes de que el acceso se "
            "bloquee por unos minutos."
        )
    return ""


@require_POST
def logout_vista(request):
    """
    Cierra la sesión. Solo por POST.

    Si bastara con abrir la dirección, una página ajena con un
    `<img src="/salir/">` echaría al docente a mitad del llamado de
    asistencia. Por eso el botón de la barra lateral es un formulario.
    """
    anotar(request, Evento.SALIDA)
    logout(request)
    messages.info(request, "Cerraste sesión correctamente.")
    return redirect("login")


@login_required
def mi_cuenta(request):
    """
    Cambiar la propia contraseña y el propio nombre de usuario.

    El administrador no tiene ficha de docente, asi que no sale en la
    tabla del panel: este es el unico sitio donde puede cambiar su
    usuario. Los dos formularios van separados, porque cambiar el
    usuario no deberia obligar a escribir una contraseña nueva.
    """
    if request.method == "POST":
        if request.POST.get("accion") == "usuario":
            _cambiar_mi_usuario(request)
        else:
            if _cambiar_mi_clave(request):
                return redirect("cursos")

    return render(
        request,
        "cambiar_clave.html",
        {
            "titulo": "Mi cuenta",
            "seccion": "cuenta",
            # Con esto puesto, la pantalla explica que no se puede seguir
            # hasta elegir una contraseña propia.
            "clave_pendiente": request.user.debe_cambiar_clave,
        },
    )


def _cambiar_mi_usuario(request):
    """Cambia el nombre de usuario con el que entra quien está dentro."""
    username = (request.POST.get("username") or "").strip()
    if not username:
        messages.error(request, "Escribe el nuevo nombre de usuario.")
        return
    if username == request.user.username:
        messages.info(request, "Ese ya es tu nombre de usuario.")
        return
    if Usuario.objects.filter(username=username).exclude(pk=request.user.pk).exists():
        messages.error(request, f"El usuario «{username}» ya está en uso.")
        return

    # Se exige la contraseña: sin ella, cualquiera que encuentre una
    # sesión abierta podría quedarse con la cuenta.
    if not request.user.check_password(request.POST.get("password_confirma") or ""):
        messages.error(request, "Para cambiar el usuario escribe tu contraseña actual.")
        return

    anterior = request.user.username
    request.user.username = username
    request.user.save(update_fields=["username"])
    anotar(request, Evento.USUARIO_PROPIO, usuario=anterior, detalle=f"ahora entra como {username}")
    messages.success(request, f"Ahora entras con el usuario «{username}».")


def _cambiar_mi_clave(request):
    """Cambia la contraseña propia. Devuelve True si se guardó."""
    actual = request.POST.get("password_actual") or ""
    nueva = request.POST.get("password_nueva") or ""

    if not request.user.check_password(actual):
        messages.error(request, "La contraseña actual no es correcta.")
        return False
    try:
        validate_password(nueva, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return False

    request.user.poner_clave_propia(nueva)
    request.user.save(update_fields=["password", "debe_cambiar_clave"])
    update_session_auth_hash(request, request.user)
    anotar(request, Evento.CLAVE_PROPIA)
    messages.success(request, "Contraseña actualizada correctamente.")
    return True


# ---------------------------------------------------------------------
# Panel de administración
# ---------------------------------------------------------------------
@login_required
@solo_admin
def panel_admin(request):
    docentes = (
        Docente.objects.select_related("usuario")
        .annotate(n_grupos=Count("grupos"))
        .order_by("apellidos", "nombres")
    )
    con_clases = set(
        SesionClase.objects.values_list("docente_id", flat=True).distinct()
    )
    ficha_propia = request.user.docente

    lista = []
    for docente in docentes:
        usuario = docente.usuario
        tiene_clases = docente.id_docente in con_clases
        es_uno_mismo = ficha_propia is not None and ficha_propia.id_docente == docente.id_docente
        lista.append(
            {
                "obj": docente,
                "username": usuario.username if usuario else None,
                "tiene_clave": bool(
                    usuario and usuario.password and usuario.password != "PENDIENTE_DEFINIR"
                ),
                # Sigue usando la clave que le puso el administrador.
                "clave_pendiente": bool(usuario and usuario.debe_cambiar_clave),
                "n_grupos": docente.n_grupos,
                # Se puede borrar solo quien no deja historial huérfano.
                "se_puede_borrar": not (docente.n_grupos or tiene_clases or es_uno_mismo),
                "tiene_clases": tiene_clases,
            }
        )

    # Cursos: cada grupo con cuántos alumnos y cuántas clases lleva, para
    # poder decidir de un vistazo si se puede tocar o no.
    grupos = grupos_en_cache(request)
    alumnos_por_grupo = dict(
        Matricula.objects.filter(estado=Matricula.Estado.ACTIVA)
        .values_list("grupo_id")
        .annotate(total=Count("id_matricula"))
    )
    clases_por_grupo = dict(
        SesionClase.objects.values_list("grupo_id").annotate(total=Count("id_sesion"))
    )
    cursos = [
        {
            "grupo": grupo,
            "alumnos": alumnos_por_grupo.get(grupo.id_grupo, 0),
            "clases": clases_por_grupo.get(grupo.id_grupo, 0),
        }
        for grupo in grupos
    ]

    return render(
        request,
        "admin_panel.html",
        {
            "titulo": "Administración",
            "seccion": "admin",
            "docentes": lista,
            "grupos": grupos,
            "cursos": cursos,
            "periodos": PeriodoAcademico.objects.annotate(
                n_grupos=Count("grupos")
            ).order_by("-codigo"),
            "sin_clave": sum(1 for d in lista if not d["tiene_clave"]),
            "claves_de_reparto": sum(1 for d in lista if d["clave_pendiente"]),
            # Formulario de «Nuevo curso», que antes vivía en la portada.
            "escuelas": EscuelaProfesional.objects.select_related("facultad").all(),
            "semestres": SEMESTRES,
        },
    )


@login_required
@solo_admin
@require_POST
def crear_docente(request):
    apellidos = (request.POST.get("apellidos") or "").strip().upper()
    nombres = (request.POST.get("nombres") or "").strip().upper()
    username = (request.POST.get("username") or "").strip()
    dni = (request.POST.get("dni") or "").strip() or None
    email = (request.POST.get("email") or "").strip() or None
    clave = request.POST.get("password") or ""

    if not (apellidos and nombres and username):
        messages.error(request, "Apellidos, nombres y usuario son obligatorios.")
        return redirect("admin-panel")

    if Usuario.objects.filter(username=username).exists():
        messages.error(request, f"El usuario «{username}» ya está registrado.")
        return redirect("admin-panel")

    if dni and Docente.objects.filter(dni=dni).exists():
        messages.error(request, f"El DNI {dni} ya está registrado.")
        return redirect("admin-panel")

    if clave:
        try:
            validate_password(clave)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("admin-panel")

    usuario = Usuario(username=username, rol=Usuario.Rol.DOCENTE, is_active=True)
    if clave:
        # La eligió el administrador, no su dueño: sirve para entrar una
        # vez y el sistema le pedirá la suya.
        usuario.poner_clave_de_reparto(clave)
    else:
        usuario.password = "PENDIENTE_DEFINIR"
    usuario.save()

    Docente.objects.create(
        usuario=usuario, apellidos=apellidos, nombres=nombres,
        dni=dni, email=email, activo=True,
    )
    anotar(request, Evento.DOCENTE_CREADO, detalle=f"{apellidos} {nombres} (entra como {username})")
    messages.success(request, f"Docente «{apellidos} {nombres}» registrado.")
    if clave:
        messages.info(
            request,
            f"Entrégale la contraseña a «{apellidos} {nombres}». Al entrar, el "
            "sistema le pedirá que elija una propia.",
        )
    return redirect("admin-panel")


@login_required
@solo_admin
@require_POST
def editar_docente(request, id_docente):
    """
    Cambia los datos de un docente y el usuario con el que entra.

    Antes solo se podia tocar la contraseña: un usuario mal escrito
    obligaba a borrar la ficha y crearla de nuevo, lo que no siempre es
    posible si ya dicto clases.
    """
    docente = get_object_or_404(Docente.objects.select_related("usuario"), pk=id_docente)

    apellidos = (request.POST.get("apellidos") or "").strip().upper()
    nombres = (request.POST.get("nombres") or "").strip().upper()
    username = (request.POST.get("username") or "").strip()
    dni = (request.POST.get("dni") or "").strip() or None
    email = (request.POST.get("email") or "").strip() or None

    if not (apellidos and nombres):
        messages.error(request, "Los apellidos y los nombres son obligatorios.")
        return redirect("admin-panel")

    if dni and Docente.objects.filter(dni=dni).exclude(pk=docente.pk).exists():
        messages.error(request, f"El DNI {dni} ya está registrado en otro docente.")
        return redirect("admin-panel")

    cuenta = docente.usuario
    if username and cuenta is not None:
        repetido = Usuario.objects.filter(username=username).exclude(pk=cuenta.pk).exists()
        if repetido:
            messages.error(request, f"El usuario «{username}» ya está en uso.")
            return redirect("admin-panel")

    with transaction.atomic():
        docente.apellidos = apellidos
        docente.nombres = nombres
        docente.dni = dni
        docente.email = email
        docente.save(update_fields=["apellidos", "nombres", "dni", "email"])

        if username and cuenta is not None and cuenta.username != username:
            cuenta.username = username
            cuenta.save(update_fields=["username"])

    anotar(request, Evento.DOCENTE_EDITADO, detalle=docente.nombre_completo)
    messages.success(request, f"Datos de «{docente.nombre_completo}» actualizados.")
    return redirect("admin-panel")


@login_required
@solo_admin
@require_POST
def asignar_clave(request, id_docente):
    docente = get_object_or_404(Docente.objects.select_related("usuario"), pk=id_docente)
    if docente.usuario_id is None:
        messages.error(request, "Este docente no tiene una cuenta de acceso asociada.")
        return redirect("admin-panel")

    clave = request.POST.get("password") or ""
    try:
        validate_password(clave)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("admin-panel")

    docente.usuario.poner_clave_de_reparto(clave)
    docente.usuario.save(update_fields=["password", "debe_cambiar_clave"])
    anotar(request, Evento.CLAVE_ASIGNADA, detalle=f"a {docente.usuario.username}")
    messages.success(
        request,
        f"Contraseña asignada a «{docente.usuario.username}». Al entrar, el "
        "sistema le pedirá que elija una propia.",
    )
    return redirect("admin-panel")


@login_required
@solo_admin
@require_POST
def eliminar_docente(request, id_docente):
    """
    Borra la ficha de un docente y su cuenta de acceso.

    No se permite si tiene cursos asignados o clases dictadas. Una sesión
    de clase guarda en `id_docente` quién la dictó: es el registro oficial
    del curso, y borrar al docente dejaría ese historial sin dueño. En ese
    caso lo correcto es reasignar el curso, no eliminar a la persona.
    """
    docente = get_object_or_404(Docente.objects.select_related("usuario"), pk=id_docente)

    propia = request.user.docente
    if propia is not None and propia.id_docente == docente.id_docente:
        messages.error(request, "No puedes eliminar tu propia ficha de docente.")
        return redirect("admin-panel")

    cursos = Grupo.objects.filter(docente_id=docente.pk).count()
    if cursos:
        messages.error(
            request,
            f"«{docente.nombre_completo}» tiene {cursos} "
            f"{'curso asignado' if cursos == 1 else 'cursos asignados'}. "
            "Asígnaselos antes a otro docente, en «Grupos y docente asignado».",
        )
        return redirect("admin-panel")

    clases = SesionClase.objects.filter(docente_id=docente.pk).count()
    if clases:
        messages.error(
            request,
            f"«{docente.nombre_completo}» dictó {clases} "
            f"{'clase registrada' if clases == 1 else 'clases registradas'}. "
            "Su nombre forma parte del registro oficial de esas clases, así "
            "que no se puede eliminar.",
        )
        return redirect("admin-panel")

    nombre = docente.nombre_completo
    cuenta = docente.usuario
    with transaction.atomic():
        docente.delete()
        # La cuenta se va con la ficha, salvo que sea de administrador:
        # esa sirve para entrar al panel aunque no dicte nada.
        if cuenta is not None and not cuenta.es_admin:
            cuenta.delete()

    anotar(request, Evento.DOCENTE_ELIMINADO, detalle=nombre)
    messages.success(request, f"Docente «{nombre}» eliminado.")
    return redirect("admin-panel")


@login_required
@solo_admin
@require_POST
def asignar_docente(request, id_grupo):
    grupo = get_object_or_404(Grupo.objects.select_related("curso"), pk=id_grupo)

    docente = docente_por_id(request.POST.get("id_docente"))
    if docente is None:
        messages.error(request, "El docente indicado no existe.")
        return redirect("admin-panel")

    grupo.docente = docente
    grupo.save(update_fields=["docente"])
    anotar(
        request,
        Evento.DOCENTE_ASIGNADO,
        detalle=f"{grupo.curso.codigo} · {grupo.nombre} → {docente.nombre_completo}",
    )
    messages.success(request, "Docente asignado al grupo.")
    return redirect("admin-panel")


# ---------------------------------------------------------------------
# Registro de seguridad
# ---------------------------------------------------------------------
@login_required
@solo_admin
def registro_seguridad(request):
    """
    Lo que ha pasado en el sistema, lo más reciente arriba.

    Dos preguntas que antes no tenían respuesta: quién eliminó un curso, y
    si alguien está probando contraseñas. Lo segundo se ve de un vistazo
    en el resumen de arriba: varios intentos fallidos seguidos desde la
    misma IP no son un docente que se equivocó al escribir.
    """
    ver = request.GET.get("ver") or "todo"
    eventos = EventoSeguridad.objects.all()
    if ver == "accesos":
        eventos = eventos.filter(tipo__in=[e for e in Evento.values if e.startswith("LOGIN")])
    elif ver == "fallidos":
        eventos = eventos.filter(tipo__in=[Evento.LOGIN_FALLIDO, Evento.LOGIN_BLOQUEADO])
    elif ver == "cambios":
        eventos = eventos.exclude(tipo__in=[Evento.LOGIN_OK, Evento.LOGIN_FALLIDO,
                                            Evento.LOGIN_BLOQUEADO, Evento.SALIDA])

    desde_ayer = timezone.now() - timedelta(hours=24)
    del_dia = EventoSeguridad.objects.filter(momento__gte=desde_ayer)

    return render(
        request,
        "seguridad.html",
        {
            "titulo": "Registro de seguridad",
            "seccion": "seguridad",
            "ver": ver,
            # Un tope fijo: esta pantalla es para mirar lo último, no para
            # arrastrar miles de filas al navegador del aula.
            "eventos": eventos[:EVENTOS_EN_PANTALLA],
            "tope": EVENTOS_EN_PANTALLA,
            "total": EventoSeguridad.objects.count(),
            "entradas_hoy": del_dia.filter(tipo=Evento.LOGIN_OK).count(),
            "fallos_hoy": del_dia.filter(tipo=Evento.LOGIN_FALLIDO).count(),
            "bloqueos_hoy": del_dia.filter(tipo=Evento.LOGIN_BLOQUEADO).count(),
            "ips_con_fallos": (
                del_dia.filter(tipo=Evento.LOGIN_FALLIDO)
                .values("ip")
                .annotate(veces=Count("id_evento"))
                .order_by("-veces")[:5]
            ),
            "dias_que_se_guarda": DIAS_QUE_SE_GUARDA,
        },
    )
