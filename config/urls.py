"""Rutas del sistema de asistencia."""
from django.urls import path

from academico import gestion as academico_gestion
from academico import views as academico
from asistencia import views as asistencia
from cuentas import views as cuentas
from reportes import views as reportes

urlpatterns = [
    # ------------------------------ Acceso ------------------------------
    path("login/", cuentas.login_vista, name="login"),
    path("salir/", cuentas.logout_vista, name="logout"),
    path("mi-cuenta/", cuentas.mi_cuenta, name="cambiar-clave"),

    # ------------------------------ Cursos ------------------------------
    path("", academico.cursos, name="cursos"),
    path("cursos/nuevo/", academico_gestion.crear_curso, name="crear-curso"),
    path("grupos/<int:id_grupo>/editar/", academico_gestion.editar_curso, name="editar-curso"),
    path("grupos/<int:id_grupo>/eliminar/", academico_gestion.eliminar_curso, name="eliminar-curso"),

    # ---------------------------- Matrículas ----------------------------
    path("grupos/<int:id_grupo>/matriculados/", academico.matriculados, name="matriculados"),
    path("grupos/<int:id_grupo>/matricular/", academico_gestion.matricular, name="matricular"),
    path(
        "grupos/<int:id_grupo>/matriculas/<int:id_matricula>/quitar/",
        academico_gestion.quitar_matricula,
        name="quitar-matricula",
    ),
    path(
        "grupos/<int:id_grupo>/estudiantes/importar/",
        academico_gestion.importar_estudiantes,
        name="importar-estudiantes",
    ),

    # ---------------------------- Asistencia ----------------------------
    path("grupos/<int:id_grupo>/asistencia/", asistencia.llamar_asistencia, name="asistencia"),
    path("grupos/<int:id_grupo>/historial/", asistencia.historial, name="historial"),
    path("sesiones/<int:id_sesion>/", asistencia.sesion_detalle, name="sesion"),
    path("sesiones/<int:id_sesion>/cerrar/", asistencia.cerrar_sesion_vista, name="cerrar-sesion"),
    path("sesiones/<int:id_sesion>/eliminar/", academico_gestion.eliminar_sesion, name="eliminar-sesion"),

    # ----------------------------- Reportes -----------------------------
    path("grupos/<int:id_grupo>/reporte/", reportes.reporte, name="reporte"),
    path("grupos/<int:id_grupo>/exportar/<str:formato>/", reportes.exportar, name="exportar"),
    path(
        "sesiones/<int:id_sesion>/exportar/<str:formato>/",
        reportes.exportar_sesion,
        name="exportar-sesion",
    ),
    path("exportar/consolidado/", reportes.exportar_general, name="exportar-consolidado"),

    # --------------------------- Administración --------------------------
    path("administracion/", cuentas.panel_admin, name="admin-panel"),
    path("administracion/docentes/nuevo/", cuentas.crear_docente, name="admin-crear-docente"),
    path("administracion/docentes/<int:id_docente>/clave/", cuentas.asignar_clave, name="admin-clave"),
    path(
        "administracion/docentes/<int:id_docente>/editar/",
        cuentas.editar_docente,
        name="admin-editar-docente",
    ),
    path(
        "administracion/docentes/<int:id_docente>/eliminar/",
        cuentas.eliminar_docente,
        name="admin-eliminar-docente",
    ),
    path("administracion/grupos/<int:id_grupo>/docente/", cuentas.asignar_docente, name="admin-asignar-docente"),
    path("administracion/periodos/nuevo/", academico_gestion.crear_periodo, name="admin-crear-periodo"),

    # ----------------------------- Seguridad -----------------------------
    path("seguridad/", cuentas.registro_seguridad, name="seguridad"),
]

handler403 = "config.errores.acceso_denegado"
handler404 = "config.errores.pagina_no_encontrada"
handler500 = "config.errores.error_del_servidor"
