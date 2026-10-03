"""
Validaciones de formulario y traducción de errores de MySQL.

Todo lo de aquí es lógica pura: `SimpleTestCase` no abre la base de datos,
así que estas pruebas corren aunque MySQL esté apagado.
"""
import datetime

from django.test import SimpleTestCase

from academico.gestion import _creditos, _fecha, _limpiar, _semestre, leer_lista_de_estudiantes
from asistencia.errores import ErrorDeNegocio, mensaje_de_error_mysql
from asistencia.models import LETRA_ESTADO, EstadoAsistencia
from asistencia.services import _normalizar_estado
from reportes.datos import clasificar


class LeerListaDeEstudiantes(SimpleTestCase):
    def test_acepta_punto_y_coma_y_pasa_a_mayusculas(self):
        fichas, errores = leer_lista_de_estudiantes("266197;quispe;mamani;juan carlos")
        self.assertEqual(errores, [])
        self.assertEqual(
            fichas,
            [{"codigo": "266197", "apellido_paterno": "QUISPE",
              "apellido_materno": "MAMANI", "nombres": "JUAN CARLOS", "email": None}],
        )

    def test_acepta_tabulador_al_pegar_desde_excel(self):
        fichas, errores = leer_lista_de_estudiantes("266197\tQUISPE\tMAMANI\tJUAN")
        self.assertEqual(errores, [])
        self.assertEqual(fichas[0]["codigo"], "266197")

    def test_el_correo_es_opcional(self):
        fichas, _ = leer_lista_de_estudiantes("266197;Q;M;J;juan@unap.edu.pe")
        self.assertEqual(fichas[0]["email"], "juan@unap.edu.pe")

    def test_el_apellido_materno_puede_ir_vacio(self):
        fichas, errores = leer_lista_de_estudiantes("266473;FLORES;;ANA")
        self.assertEqual(errores, [])
        self.assertEqual(fichas[0]["apellido_materno"], "")

    def test_ignora_lineas_en_blanco(self):
        fichas, errores = leer_lista_de_estudiantes("\n\n266197;Q;M;J\n   \n")
        self.assertEqual(len(fichas), 1)
        self.assertEqual(errores, [])

    def test_avisa_de_columnas_faltantes_con_el_numero_de_linea(self):
        _, errores = leer_lista_de_estudiantes("266197;QUISPE;MAMANI")
        self.assertEqual(len(errores), 1)
        self.assertIn("Línea 1", errores[0])

    def test_rechaza_codigos_repetidos_dentro_del_mismo_pegado(self):
        fichas, errores = leer_lista_de_estudiantes("266197;Q;M;J\n266197;X;Y;Z")
        self.assertEqual(len(fichas), 1)
        self.assertIn("repetido", errores[0])

    def test_exige_apellido_paterno_y_nombres(self):
        _, errores = leer_lista_de_estudiantes("266197;;MAMANI;")
        self.assertEqual(len(errores), 1)
        self.assertIn("obligatorios", errores[0])

    def test_rechaza_valores_mas_largos_que_la_columna(self):
        _, errores = leer_lista_de_estudiantes("1234567890123;Q;M;J")
        self.assertEqual(len(errores), 1)
        self.assertIn("codigo", errores[0])

    def test_las_lineas_buenas_pasan_aunque_otras_fallen(self):
        fichas, errores = leer_lista_de_estudiantes("mala\n266197;Q;M;J\ntambien mala")
        self.assertEqual(len(fichas), 1)
        self.assertEqual(len(errores), 2)


class ValidadoresDeCurso(SimpleTestCase):
    def test_creditos_acepta_coma_y_punto(self):
        self.assertEqual(str(_creditos("2,5")), "2.50")
        self.assertEqual(str(_creditos("2.5")), "2.50")

    def test_creditos_rechaza_cero_negativos_y_texto(self):
        for valor in ("0", "-1", "abc", "", None, "100"):
            self.assertIsNone(_creditos(valor), valor)

    def test_semestre_solo_del_uno_al_diez(self):
        self.assertEqual(_semestre("3"), 3)
        for valor in ("0", "11", "x", None):
            self.assertIsNone(_semestre(valor), valor)

    def test_fecha_iso_o_nada(self):
        self.assertEqual(_fecha("2026-04-01"), datetime.date(2026, 4, 1))
        for valor in ("", None, "01/04/2026", "no es fecha"):
            self.assertIsNone(_fecha(valor), valor)

    def test_limpiar_recorta_y_sube_a_mayusculas(self):
        self.assertEqual(_limpiar("  met201 ", mayusculas=True), "MET201")
        self.assertEqual(_limpiar("  met201 "), "met201")
        self.assertEqual(_limpiar(None), "")


class EstadosDeAsistencia(SimpleTestCase):
    def test_normaliza_minusculas_y_espacios(self):
        self.assertEqual(_normalizar_estado("  presente "), "PRESENTE")

    def test_rechaza_un_estado_inventado(self):
        with self.assertRaises(ErrorDeNegocio):
            _normalizar_estado("AUSENTE")

    def test_solo_hay_tres_estados(self):
        # Justificada y tardanza se quitaron: las dos contaban como
        # asistencia, asi que no cambiaban ningun porcentaje.
        self.assertEqual(len(EstadoAsistencia), 2)

    def test_cada_estado_tiene_su_letra(self):
        self.assertEqual(
            {LETRA_ESTADO[e] for e in EstadoAsistencia}, {"P", "F"}
        )


class TraduccionDeErroresMysql(SimpleTestCase):
    def test_un_signal_del_trigger_llega_tal_cual(self):
        # 1644 es el código de un SIGNAL de usuario: el texto ya viene en
        # español desde la base y debe mostrarse sin adornos.
        excepcion = Exception(1644, "La sesión está cerrada; no se puede modificar")
        self.assertEqual(
            mensaje_de_error_mysql(excepcion),
            "La sesión está cerrada; no se puede modificar",
        )

    def test_clave_duplicada_se_explica_en_castellano(self):
        mensaje = mensaje_de_error_mysql(Exception(1062, "Duplicate entry"))
        self.assertIn("Ya existe un registro", mensaje)

    def test_llave_foranea_se_explica_en_castellano(self):
        mensaje = mensaje_de_error_mysql(Exception(1452, "foreign key"))
        self.assertIn("no existe en la base de datos", mensaje)

    def test_lee_el_codigo_de_la_excepcion_original(self):
        original = Exception(1644, "El docente no está asignado a este grupo")
        envoltorio = Exception("algo falló")
        envoltorio.__cause__ = original
        self.assertEqual(
            mensaje_de_error_mysql(envoltorio),
            "El docente no está asignado a este grupo",
        )

    def test_un_error_desconocido_no_se_traga(self):
        mensaje = mensaje_de_error_mysql(Exception(9999, "vaya"))
        self.assertIn("vaya", mensaje)


class Semaforo(SimpleTestCase):
    def test_colores_por_tramo(self):
        self.assertEqual(clasificar(100.0), "verde")
        self.assertEqual(clasificar(85.0), "verde")
        self.assertEqual(clasificar(84.9), "ambar")
        self.assertEqual(clasificar(70.0), "ambar")
        self.assertEqual(clasificar(69.9), "rojo")
        self.assertEqual(clasificar(0.0), "rojo")

    def test_sin_clases_dictadas_no_hay_color(self):
        self.assertEqual(clasificar(None), "sin_datos")
