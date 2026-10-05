"""
Eliminar una clase abierta por error.

Lo hace solo el administrador: el docente podría borrar así una clase que
le salió mal en vez de corregirla, y la clase cerrada es el registro
oficial del curso.

Son `SimpleTestCase`: los cortes de permiso y de método ocurren antes de
tocar MySQL, así que se prueban sin base de datos.
"""
from django.core.exceptions import PermissionDenied
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from academico.gestion import eliminar_sesion
from cuentas.models import Usuario
from cuentas.seguridad import Evento, EventoSeguridad


def peticion(metodo, rol):
    p = getattr(RequestFactory(), metodo)("/sesiones/7/eliminar/")
    p.user = Usuario(username="x", rol=rol)
    return p


class LaRuta(SimpleTestCase):
    def test_lleva_a_la_vista_de_eliminar(self):
        ruta = reverse("eliminar-sesion", args=[7])
        self.assertEqual(ruta, "/sesiones/7/eliminar/")
        self.assertEqual(resolve(ruta).func, eliminar_sesion)


class SoloElAdministrador(SimpleTestCase):
    def test_el_docente_recibe_403(self):
        with self.assertRaises(PermissionDenied):
            eliminar_sesion(peticion("post", Usuario.Rol.DOCENTE), id_sesion=7)

    def test_sin_sesion_iniciada_va_al_login(self):
        p = RequestFactory().post("/sesiones/7/eliminar/")

        class Anonimo:
            is_authenticated = False

        p.user = Anonimo()
        respuesta = eliminar_sesion(p, id_sesion=7)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta["Location"])

    def test_un_enlace_no_basta_hace_falta_el_formulario(self):
        # Con GET, una imagen o un enlace en otra página borrarían la clase.
        respuesta = eliminar_sesion(peticion("get", Usuario.Rol.ADMIN), id_sesion=7)
        self.assertEqual(respuesta.status_code, 405)


class QuedaEnElRegistro(SimpleTestCase):
    def test_sale_en_rojo_como_las_demas_eliminaciones(self):
        evento = EventoSeguridad(tipo=Evento.CLASE_ELIMINADA)
        self.assertEqual(evento.insignia, "ins-rojo")
        self.assertEqual(evento.get_tipo_display(), "Eliminó una clase")

    def test_el_nombre_cabe_en_la_columna(self):
        # `evento_seguridad.tipo` es VARCHAR(30).
        self.assertLessEqual(len(Evento.CLASE_ELIMINADA.value), 30)


class ElBotonDelHistorial(SimpleTestCase):
    def test_solo_aparece_para_el_administrador_y_pide_confirmar(self):
        fuente = get_template("historial.html").template.source
        inicio = fuente.index("{% if user.es_admin %}")
        bloque = fuente[inicio:fuente.index("{% endif %}\n", fuente.index("</form>", inicio))]
        self.assertIn("eliminar-sesion", bloque)
        self.assertIn('method="post"', bloque)
        self.assertIn("data-confirmar=", bloque)
        self.assertIn("{% csrf_token %}", bloque)
