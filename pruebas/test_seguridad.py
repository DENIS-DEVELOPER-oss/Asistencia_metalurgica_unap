"""
Comprobaciones de acceso que no necesitan base de datos.

Tres cosas se prueban aquí: que el parámetro `next` no saque al docente
del sistema, que el límite de intentos frene el tanteo de contraseñas, y
que las cabeceras que protegen la página salgan en cada respuesta.
"""
from datetime import timedelta

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone

from config.middleware import CabecerasDeSeguridad, nonce_para_plantillas
from cuentas.seguridad import (
    LIMITE_POR_IP,
    LIMITE_POR_USUARIO,
    VENTANA,
    Evento,
    anotar,
    decidir,
    ip_de,
)
from cuentas.views import destino_tras_entrar


class DestinoTrasEntrar(SimpleTestCase):
    def setUp(self):
        self.peticiones = RequestFactory()

    def destino(self, url, metodo="get"):
        if metodo == "post":
            return destino_tras_entrar(self.peticiones.post("/login/", {"next": url}))
        return destino_tras_entrar(self.peticiones.get("/login/", {"next": url}))

    def test_acepta_una_ruta_del_propio_sitio(self):
        self.assertEqual(self.destino("/grupos/3/asistencia/"), "/grupos/3/asistencia/")

    def test_lo_mismo_cuando_viaja_en_el_post(self):
        self.assertEqual(self.destino("/grupos/3/reporte/", "post"), "/grupos/3/reporte/")

    def test_rechaza_un_sitio_externo(self):
        self.assertIsNone(self.destino("https://sitio-falso.com/login"))

    def test_rechaza_una_url_sin_esquema(self):
        self.assertIsNone(self.destino("//sitio-falso.com"))

    def test_rechaza_javascript(self):
        self.assertIsNone(self.destino("javascript:alert(1)"))

    def test_rechaza_otro_host_aunque_parezca_el_nuestro(self):
        self.assertIsNone(self.destino("https://testserver.sitio-falso.com/"))

    def test_sin_next_devuelve_nada(self):
        self.assertIsNone(destino_tras_entrar(self.peticiones.get("/login/")))

    def test_next_vacio_devuelve_nada(self):
        self.assertIsNone(self.destino(""))


class ClaveSecreta(SimpleTestCase):
    def test_las_claves_de_fabrica_estan_listadas(self):
        from config.settings import CLAVES_DE_FABRICA

        # Las dos que reparte el proyecto tienen que estar en la lista negra,
        # o el arranque en producción no las detectaría.
        self.assertIn("django-inseguro-clave-de-desarrollo", CLAVES_DE_FABRICA)
        self.assertIn("django-inseguro-cambia-esta-clave-en-produccion", CLAVES_DE_FABRICA)

    @override_settings(DEBUG=False)
    def test_el_ejemplo_del_env_coincide_con_la_lista(self):
        import pathlib
        import re

        from django.conf import settings
        from config.settings import CLAVES_DE_FABRICA

        texto = (pathlib.Path(settings.BASE_DIR) / ".env.example").read_text(encoding="utf-8")
        clave = re.search(r"^SECRET_KEY=(.*)$", texto, re.M).group(1).strip()
        self.assertIn(clave, CLAVES_DE_FABRICA)


class LimiteDeIntentos(SimpleTestCase):
    """
    La regla que frena el tanteo de contraseñas.

    Importa aquí porque la clave inicial del docente es su DNI: ocho
    dígitos que un programa prueba en una tarde si nadie lo impide.
    """

    def setUp(self):
        self.ahora = timezone.now()

    def decidir(self, por_usuario=0, por_ip=0, hace_minutos=1):
        return decidir(
            por_usuario, por_ip, self.ahora - timedelta(minutes=hace_minutos), self.ahora
        )

    def test_un_error_al_escribir_no_bloquea_nada(self):
        self.assertEqual(self.decidir(por_usuario=1), (False, 0))

    def test_justo_por_debajo_del_limite_todavia_se_puede_entrar(self):
        bloqueado, _ = self.decidir(por_usuario=LIMITE_POR_USUARIO - 1)
        self.assertFalse(bloqueado)

    def test_al_llegar_al_limite_la_cuenta_queda_en_espera(self):
        bloqueado, minutos = self.decidir(por_usuario=LIMITE_POR_USUARIO)
        self.assertTrue(bloqueado)
        self.assertGreater(minutos, 0)

    def test_tambien_se_bloquea_por_equipo_aunque_cambie_de_usuario(self):
        # Recorrer una lista de usuarios desde la misma PC: cada cuenta
        # suma pocos fallos, pero el equipo los suma todos.
        bloqueado, _ = self.decidir(por_usuario=1, por_ip=LIMITE_POR_IP)
        self.assertTrue(bloqueado)

    def test_el_bloqueo_se_levanta_solo_al_caducar_la_ventana(self):
        viejo = int(VENTANA.total_seconds() // 60) + 1
        self.assertEqual(
            self.decidir(por_usuario=LIMITE_POR_USUARIO, hace_minutos=viejo), (False, 0)
        )

    def test_los_minutos_que_faltan_caben_en_la_ventana(self):
        _, minutos = self.decidir(por_usuario=LIMITE_POR_USUARIO, hace_minutos=1)
        self.assertLessEqual(minutos, int(VENTANA.total_seconds() // 60))

    def test_sin_fallos_anotados_no_hay_nada_que_esperar(self):
        self.assertEqual(decidir(LIMITE_POR_USUARIO, 0, None, self.ahora), (False, 0))


class DeDondeVieneLaPeticion(SimpleTestCase):
    """
    `X-Forwarded-For` solo se cree cuando hay un proxy declarado.

    Sin proxy delante, esa cabecera la escribe quien quiera: haciéndole
    caso, cualquiera esquivaría el límite por equipo cambiándola en cada
    intento.
    """

    def setUp(self):
        self.peticion = RequestFactory().post(
            "/login/", HTTP_X_FORWARDED_FOR="9.9.9.9", REMOTE_ADDR="192.168.1.40"
        )

    def test_sin_proxy_se_usa_la_conexion_real(self):
        self.assertEqual(ip_de(self.peticion), "192.168.1.40")

    @override_settings(DETRAS_DE_PROXY=True)
    def test_con_proxy_declarado_se_usa_la_cabecera(self):
        self.assertEqual(ip_de(self.peticion), "9.9.9.9")

    def test_sin_direccion_no_revienta(self):
        peticion = RequestFactory().post("/login/")
        peticion.META.pop("REMOTE_ADDR", None)
        self.assertIsNone(ip_de(peticion))


class AnotarNuncaRompeLaOperacion(SimpleTestCase):
    def test_si_la_base_falla_se_registra_el_problema_y_se_sigue(self):
        # SimpleTestCase prohíbe tocar la base, así que esto reproduce el
        # caso: eliminar un curso no puede fracasar porque no se haya
        # podido escribir su apunte.
        peticion = RequestFactory().post("/administracion/")
        with self.assertLogs("cuentas.seguridad", level="ERROR"):
            anotar(peticion, Evento.CURSO_ELIMINADO, usuario="admin")


class Autenticado:
    is_authenticated = True


class CabecerasQueProtegenLaPagina(SimpleTestCase):
    """
    La política de contenido: qué código puede ejecutar el navegador.

    Si algún día un nombre de alumno o una observación llegara a la
    página sin escapar, el `<script>` que trajera no correría: solo corre
    lo que lleva el número de un solo uso de esta petición.
    """

    def responder(self, autenticado=False):
        peticion = RequestFactory().get("/")
        if autenticado:
            peticion.user = Autenticado()

        capa = CabecerasDeSeguridad(lambda p: HttpResponse("ok"))
        return peticion, capa(peticion)

    def test_cada_peticion_trae_su_propio_numero_de_un_solo_uso(self):
        primera, _ = self.responder()
        segunda, _ = self.responder()
        self.assertNotEqual(primera.csp_nonce, segunda.csp_nonce)
        self.assertGreaterEqual(len(primera.csp_nonce), 16)

    def test_la_politica_autoriza_ese_numero_y_nada_mas(self):
        peticion, respuesta = self.responder()
        politica = respuesta["Content-Security-Policy"]
        self.assertIn(f"script-src 'self' 'nonce-{peticion.csp_nonce}'", politica)
        # Sin 'unsafe-inline' en los scripts: es lo que hace que un
        # <script> colado en la página no llegue a ejecutarse.
        guion = [r for r in politica.split("; ") if r.startswith("script-src")][0]
        self.assertNotIn("unsafe-inline", guion)

    def test_nadie_puede_meter_el_sistema_dentro_de_un_marco(self):
        _, respuesta = self.responder()
        self.assertIn("frame-ancestors 'none'", respuesta["Content-Security-Policy"])

    def test_los_formularios_solo_se_envian_a_este_sistema(self):
        _, respuesta = self.responder()
        self.assertIn("form-action 'self'", respuesta["Content-Security-Policy"])

    def test_camara_microfono_y_ubicacion_quedan_apagados(self):
        _, respuesta = self.responder()
        permisos = respuesta["Permissions-Policy"]
        for aparato in ("camera", "microphone", "geolocation"):
            with self.subTest(aparato=aparato):
                self.assertIn(f"{aparato}=()", permisos)

    def test_las_pantallas_con_datos_no_se_guardan_en_el_navegador(self):
        # En la PC del aula, tras cerrar sesión, «atrás» no debe devolver
        # la lista de alumnos.
        _, respuesta = self.responder(autenticado=True)
        self.assertIn("no-store", respuesta["Cache-Control"])

    def test_la_pantalla_de_login_si_se_puede_guardar(self):
        _, respuesta = self.responder()
        self.assertNotIn("Cache-Control", respuesta)

    def test_la_plantilla_recibe_el_numero(self):
        peticion, _ = self.responder()
        self.assertEqual(
            nonce_para_plantillas(peticion), {"csp_nonce": peticion.csp_nonce}
        )

    def test_sin_middleware_la_plantilla_no_revienta(self):
        # Las páginas de error se pintan aunque algo haya fallado antes.
        self.assertEqual(
            nonce_para_plantillas(RequestFactory().get("/")), {"csp_nonce": ""}
        )


class LasPlantillasMarcanSuCodigo(SimpleTestCase):
    """
    Un `<script>` sin nonce deja de funcionar en silencio.

    No da error en el servidor: la pantalla simplemente pierde su
    comportamiento (el tema, el buscador de alumnos, las pestañas). Por
    eso se comprueba aquí y no abriendo cada pantalla a mano.
    """

    def plantillas(self):
        import pathlib

        from django.conf import settings

        return sorted((pathlib.Path(settings.BASE_DIR) / "templates").glob("*.html"))

    def test_todo_script_de_las_plantillas_lleva_el_nonce(self):
        import re

        for plantilla in self.plantillas():
            texto = plantilla.read_text(encoding="utf-8")
            for etiqueta in re.findall(r"<script[^>]*>", texto):
                with self.subTest(plantilla=plantilla.name, etiqueta=etiqueta):
                    self.assertIn("{{ csp_nonce }}", etiqueta)

    def test_no_quedan_manejadores_escritos_dentro_del_html(self):
        # `onsubmit=`/`onclick=` no se ejecutan con la política puesta: la
        # confirmación va en `data-confirmar` y la escucha base.html.
        import re

        sospechoso = re.compile(r"\son(click|submit|change|load)\s*=")
        for plantilla in self.plantillas():
            lineas = plantilla.read_text(encoding="utf-8").splitlines()
            for numero, linea in enumerate(lineas, start=1):
                if linea.lstrip().startswith(("//", "/*", "*")):
                    continue  # comentarios del propio JavaScript
                with self.subTest(plantilla=plantilla.name, linea=numero):
                    self.assertIsNone(sospechoso.search(linea))
