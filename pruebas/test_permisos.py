"""
Quién puede llamar asistencia.

Regla: la sesión de clase se firma en `sesion_clase.id_docente`, así que
solo la abre y la marca el docente asignado al grupo. El administrador
gestiona cursos, matrículas y docentes, y consulta todo, pero no llama
lista por nadie.

Son `SimpleTestCase`: se comprueban las funciones de `academico.acceso`
con objetos en memoria, sin abrir MySQL.
"""
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from academico.acceso import docente_titular, es_docente_titular
from academico.models import Grupo
from cuentas.models import Docente, Usuario


def usuario(rol, ficha=None):
    """Usuario sin guardar, con o sin ficha de docente asociada."""
    u = Usuario(username="x", rol=rol)
    # `Usuario.docente` lee `ficha_docente`; se puede simular sin tocar la base.
    if ficha is not None:
        u.ficha_docente = ficha
    return u


ROSA = Docente(id_docente=1, apellidos="ALVAREZ", nombres="RUBY")
LUIS = Docente(id_docente=2, apellidos="MAMANI", nombres="LUIS")
GRUPO = Grupo(id_grupo=1, docente_id=1, nombre="GRUPO B")


class EsDocenteTitular(SimpleTestCase):
    def test_el_docente_asignado_sí_lo_es(self):
        self.assertTrue(es_docente_titular(usuario(Usuario.Rol.DOCENTE, ROSA), GRUPO))

    def test_otro_docente_no_lo_es(self):
        self.assertFalse(es_docente_titular(usuario(Usuario.Rol.DOCENTE, LUIS), GRUPO))

    def test_el_administrador_sin_ficha_no_lo_es(self):
        # Es el caso que motivó el cambio: el ADMIN veía el botón y abría
        # clase «en nombre de» la docente titular.
        self.assertFalse(es_docente_titular(usuario(Usuario.Rol.ADMIN), GRUPO))

    def test_un_administrador_que_ademas_dicta_el_grupo_si_lo_es(self):
        # Manda la asignación del grupo, no el rol de la cuenta.
        self.assertTrue(es_docente_titular(usuario(Usuario.Rol.ADMIN, ROSA), GRUPO))

    def test_una_cuenta_sin_ficha_de_docente_no_lo_es(self):
        self.assertFalse(es_docente_titular(usuario(Usuario.Rol.DOCENTE), GRUPO))


class DocenteTitular(SimpleTestCase):
    def test_devuelve_la_ficha_del_titular(self):
        self.assertIs(docente_titular(usuario(Usuario.Rol.DOCENTE, ROSA), GRUPO), ROSA)

    def test_corta_con_403_a_quien_no_dicta_el_grupo(self):
        for cuenta in (
            usuario(Usuario.Rol.ADMIN),
            usuario(Usuario.Rol.DOCENTE, LUIS),
            usuario(Usuario.Rol.DOCENTE),
        ):
            with self.subTest(rol=cuenta.rol, ficha=cuenta.docente):
                with self.assertRaises(PermissionDenied):
                    docente_titular(cuenta, GRUPO)

    def test_el_mensaje_explica_como_arreglarlo(self):
        with self.assertRaises(PermissionDenied) as error:
            docente_titular(usuario(Usuario.Rol.ADMIN), GRUPO)
        mensaje = str(error.exception)
        self.assertIn("Solo el docente asignado", mensaje)
        self.assertIn("Administración", mensaje)
