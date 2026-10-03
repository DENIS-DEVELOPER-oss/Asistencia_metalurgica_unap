"""
Las protecciones añadidas después de la primera revisión de seguridad.

Todo aquí corre sin MySQL: se prueban las reglas y las órdenes que se le
mandarían a la base, no la base misma.
"""
import pathlib
import re

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from config.middleware import ClavePendienteDeCambio
from cuentas.management.commands.crear_usuario_mysql import EQUIPOS, PERMISOS
from cuentas.management.commands.crear_usuario_mysql import Command as CrearUsuario
from cuentas.management.commands._herramientas_mysql import clave_fuerte, escribir_en_env
from cuentas.models import Usuario


class NadieSigueConLaClaveQueLePusieron(SimpleTestCase):
    """
    Una clave que puso el administrador sirve para entrar una vez.

    La de reparto de un docente es su DNI: la conoce quien la asignó y
    cualquiera que tenga el dato. Mientras siga puesta, la asistencia
    firmada a su nombre no prueba que fuera él.
    """

    def setUp(self):
        self.peticiones = RequestFactory()
        self.capa = ClavePendienteDeCambio(lambda p: HttpResponse("la pantalla"))

    def pedir(self, ruta, pendiente=True, autenticado=True):
        peticion = self.peticiones.get(ruta)
        peticion.user = Usuario(
            username="01340274", debe_cambiar_clave=pendiente
        ) if autenticado else None
        if not autenticado:
            class Anonimo:
                is_authenticated = False
            peticion.user = Anonimo()
        return self.capa(peticion)

    def test_con_la_clave_pendiente_no_se_llega_a_los_cursos(self):
        respuesta = self.pedir("/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], "/mi-cuenta/")

    def test_tampoco_al_llamado_de_asistencia(self):
        # Lo que de verdad importa: la firma de la asistencia.
        self.assertEqual(self.pedir("/grupos/1/asistencia/").status_code, 302)

    def test_ni_escribiendo_la_direccion_de_administracion(self):
        self.assertEqual(self.pedir("/administracion/").status_code, 302)

    def test_la_pantalla_de_cambiar_la_clave_si_se_abre(self):
        # Si no, el redirigido daría vueltas sin poder arreglarlo nunca.
        self.assertEqual(self.pedir("/mi-cuenta/").status_code, 200)

    def test_y_siempre_se_puede_salir(self):
        self.assertEqual(self.pedir("/salir/").status_code, 200)

    def test_quien_ya_eligio_la_suya_pasa_sin_estorbos(self):
        self.assertEqual(self.pedir("/", pendiente=False).status_code, 200)

    def test_a_quien_no_ha_entrado_no_le_afecta(self):
        self.assertEqual(self.pedir("/login/", autenticado=False).status_code, 200)


class MarcarLaClaveSegunQuienLaEligio(SimpleTestCase):
    def test_la_que_pone_el_administrador_queda_pendiente(self):
        cuenta = Usuario(username="nuevo")
        cuenta.poner_clave_de_reparto("12345678")
        self.assertTrue(cuenta.debe_cambiar_clave)
        self.assertTrue(cuenta.check_password("12345678"))

    def test_la_que_pone_su_dueno_no_queda_pendiente(self):
        cuenta = Usuario(username="nuevo", debe_cambiar_clave=True)
        cuenta.poner_clave_propia("una-mia-larga")
        self.assertFalse(cuenta.debe_cambiar_clave)
        self.assertTrue(cuenta.check_password("una-mia-larga"))

    def test_la_clave_nunca_se_guarda_en_claro(self):
        cuenta = Usuario(username="nuevo")
        cuenta.poner_clave_de_reparto("12345678")
        self.assertNotIn("12345678", cuenta.password)
        self.assertTrue(cuenta.password.startswith("pbkdf2_sha256$"))


class SalirSoloPorPost(SimpleTestCase):
    """
    Con un enlace, una página ajena echaría al docente del sistema.

    Bastaría un `<img src="/salir/">` en cualquier web abierta en otra
    pestaña para cerrarle la sesión a mitad del llamado de asistencia.
    """

    def test_abrir_la_direccion_no_cierra_la_sesion(self):
        from cuentas.views import logout_vista

        respuesta = logout_vista(RequestFactory().get("/salir/"))
        self.assertEqual(respuesta.status_code, 405)

    def test_en_las_plantillas_es_un_formulario_y_no_un_enlace(self):
        for plantilla in (pathlib.Path(settings.BASE_DIR) / "templates").glob("*.html"):
            texto = plantilla.read_text(encoding="utf-8")
            for enlace in re.findall(r"<a [^>]*>", texto):
                with self.subTest(plantilla=plantilla.name):
                    self.assertNotIn("'logout'", enlace)


class LaCuentaDeMysqlSoloPuedeLoNecesario(SimpleTestCase):
    """
    Todo el control de acceso del sistema vive dentro de la aplicación.

    Quien se conecta por debajo a MySQL se lo salta entero: los
    disparadores que impiden tocar una clase cerrada protegen a la
    aplicación, no a la base. Por eso la cuenta con la que trabaja no
    puede cambiar la estructura ni asomarse a otras bases.
    """

    def setUp(self):
        self.ordenes = CrearUsuario().sentencias("app_prueba", "secreta", "asistencia_unap")
        self.texto = "\n".join(self.ordenes)

    def test_no_puede_cambiar_la_estructura_de_la_base(self):
        for permiso in ("DROP", "ALTER", "CREATE TABLE", "INDEX", "REFERENCES"):
            with self.subTest(permiso=permiso):
                self.assertNotIn(permiso, PERMISOS)

    def test_no_puede_quitar_las_reglas_que_protegen_la_asistencia(self):
        # Con TRIGGER podría borrar el disparador que impide modificar una
        # clase ya cerrada, que es el que sostiene el registro oficial.
        self.assertNotIn("TRIGGER", PERMISOS)

    def test_no_puede_darse_permisos_a_si_misma(self):
        self.assertNotIn("GRANT OPTION", PERMISOS)
        self.assertNotIn("SUPER", PERMISOS)
        self.assertNotIn("WITH GRANT OPTION", self.texto)

    def test_si_puede_hacer_lo_que_el_sistema_necesita(self):
        for permiso in ("SELECT", "INSERT", "UPDATE", "DELETE", "EXECUTE"):
            with self.subTest(permiso=permiso):
                self.assertIn(permiso, PERMISOS)

    def test_los_permisos_valen_solo_para_esta_base(self):
        for orden in self.ordenes:
            if orden.startswith("GRANT"):
                with self.subTest(orden=orden):
                    self.assertIn("`asistencia_unap`.*", orden)
                    self.assertNotIn(" ON *.*", orden)

    def test_no_se_puede_entrar_con_ella_desde_la_red(self):
        self.assertEqual(set(EQUIPOS), {"localhost", "127.0.0.1"})
        self.assertNotIn("'%'", self.texto)

    def test_volver_a_ejecutarlo_cambia_la_clave_en_vez_de_fallar(self):
        # Hace falta el día que haya que rotar la contraseña.
        self.assertIn("CREATE OR REPLACE USER", self.texto)


class ContrasenaGenerada(SimpleTestCase):
    def test_es_larga_y_distinta_cada_vez(self):
        self.assertGreaterEqual(len(clave_fuerte()), 24)
        self.assertNotEqual(clave_fuerte(), clave_fuerte())

    def test_no_lleva_caracteres_que_rompan_el_env_ni_la_consola(self):
        for _ in range(50):
            clave = clave_fuerte()
            for prohibido in ("'", '"', "\\", "$", "`", " ", "\n", "="):
                with self.subTest(caracter=prohibido):
                    self.assertNotIn(prohibido, clave)


class EscribirEnElEnv(SimpleTestCase):
    """
    El .env se edita conservando sus explicaciones.

    Reescribirlo entero perdería los comentarios, que son lo que permite a
    otra persona entender el archivo dentro de un año.
    """

    def archivo(self, contenido):
        import tempfile

        ruta = pathlib.Path(tempfile.mkdtemp()) / ".env"
        ruta.write_text(contenido, encoding="utf-8")
        return ruta

    def test_cambia_el_valor_y_deja_el_comentario(self):
        ruta = self.archivo("# la cuenta de MySQL\nDB_USER=root\nDB_PORT=3306\n")
        escribir_en_env({"DB_USER": "asistencia_app"}, ruta)
        texto = ruta.read_text(encoding="utf-8")
        self.assertIn("# la cuenta de MySQL", texto)
        self.assertIn("DB_USER=asistencia_app", texto)
        self.assertNotIn("DB_USER=root", texto)
        self.assertIn("DB_PORT=3306", texto)

    def test_anade_al_final_lo_que_no_estaba(self):
        ruta = self.archivo("DEBUG=False\n")
        escribir_en_env({"DB_PASSWORD": "xyz"}, ruta)
        self.assertIn("DB_PASSWORD=xyz", ruta.read_text(encoding="utf-8"))

    def test_no_revive_una_linea_comentada(self):
        # `# DB_USER=otro` es una nota, no la configuración: si se tomara
        # por tal, el valor real se escribiría en el sitio equivocado.
        ruta = self.archivo("# DB_USER=otro\nDB_USER=root\n")
        escribir_en_env({"DB_USER": "app"}, ruta)
        texto = ruta.read_text(encoding="utf-8")
        self.assertIn("# DB_USER=otro", texto)
        self.assertIn("DB_USER=app", texto)
