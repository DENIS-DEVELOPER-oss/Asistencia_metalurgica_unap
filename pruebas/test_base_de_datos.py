"""
El instalador SQL contra los modelos de Django.

`managed = False` significa que Django no crea ni corrige el esquema: si el
script y los modelos se separan, nadie avisa hasta que una pantalla falla en
producción. Estas pruebas leen el .sql y comparan, sin necesidad de MySQL.
"""
import pathlib
import re

from django.apps import apps
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.test import SimpleTestCase

# Las apps de django.contrib no tienen tablas aquí: las migraciones están
# apagadas y las sesiones viajan firmadas en la cookie.
APPS_PROPIAS = {"cuentas", "academico", "asistencia", "reportes"}

RUTA = pathlib.Path(settings.BASE_DIR) / "base_de_datos" / "asistencia_unap_instalar.sql"


def leer():
    crudo = RUTA.read_bytes()
    return crudo, crudo.decode("utf-8")


def sin_comentarios(sql):
    """Solo lo que MySQL llega a ejecutar."""
    return "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))


def tablas_del_script(sql):
    tablas = {}
    for m in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\r?\n\) ENGINE", sql, re.S):
        columnas = set()
        for linea in m.group(2).splitlines():
            linea = linea.strip()
            if not linea or linea.startswith(("UNIQUE", "INDEX", "CONSTRAINT", "PRIMARY", "--")):
                continue
            nombre = re.match(r"(\w+)\s", linea)
            if nombre:
                columnas.add(nombre.group(1))
        tablas[m.group(1)] = columnas
    return tablas


def vistas_del_script(sql):
    vistas = {}
    # `;\s*$` y no `;\n`: guardar el archivo con finales CRLF hacía que la
    # vista dejara de encontrarse y la prueba culpaba al esquema.
    for m in re.finditer(r"CREATE OR REPLACE VIEW (\w+) AS(.*?);\s*$", sql, re.S | re.M):
        cuerpo = m.group(2)
        vistas[m.group(1)] = (
            set(re.findall(r"\bAS\s+(\w+)\s*[,\n]", cuerpo))
            | set(re.findall(r"\b\w+\.(\w+)\s*,", cuerpo))
        )
    return vistas


class ElArchivoExiste(SimpleTestCase):
    def test_esta_donde_lo_buscan_los_scripts(self):
        self.assertTrue(RUTA.is_file(), f"falta {RUTA}")

    def test_es_utf8_y_sin_bom(self):
        crudo, sql = leer()
        # Un BOM al principio hace que el cliente de MySQL se coma la
        # primera sentencia o la trate como dato.
        self.assertFalse(crudo.startswith(b"\xef\xbb\xbf"))
        self.assertIn("MINERÍA GENERAL", sql)
        self.assertIn("SUAÑA", sql)


class EsquemaContraModelos(SimpleTestCase):
    """Lo que de verdad importa: que la aplicación encuentre sus columnas."""

    def setUp(self):
        _, self.sql = leer()
        self.tablas = tablas_del_script(self.sql)
        self.vistas = vistas_del_script(self.sql)

    def test_cada_modelo_tiene_su_tabla_o_vista(self):
        for modelo in apps.get_models():
            if modelo._meta.app_label not in APPS_PROPIAS:
                continue
            tabla = modelo._meta.db_table
            with self.subTest(modelo=modelo.__name__):
                self.assertTrue(
                    tabla in self.tablas or tabla in self.vistas,
                    f"`{tabla}` no está en el instalador",
                )

    def test_cada_columna_de_cada_modelo_existe(self):
        for modelo in apps.get_models():
            if modelo._meta.app_label not in APPS_PROPIAS:
                continue
            tabla = modelo._meta.db_table
            disponibles = self.tablas.get(tabla) or self.vistas.get(tabla) or set()
            for campo in modelo._meta.fields:
                columna = campo.db_column or campo.attname
                with self.subTest(modelo=modelo.__name__, columna=columna):
                    self.assertIn(columna, disponibles)

    def test_las_claves_foraneas_apuntan_a_tablas_que_existen(self):
        for destino in re.findall(r"REFERENCES (\w+)\(", self.sql):
            with self.subTest(tabla=destino):
                self.assertIn(destino, self.tablas)

    def test_estan_todas_las_tablas_por_su_nombre(self):
        # Contarlas no decia cual faltaba; con los nombres, el fallo se lee.
        self.assertEqual(
            set(self.tablas),
            {
                "facultad", "escuela_profesional", "periodo_academico",
                "usuario", "docente", "curso", "grupo", "estudiante",
                "matricula", "sesion_clase", "asistencia",
                "evento_seguridad",
            },
        )

    def test_estan_las_tres_vistas(self):
        self.assertEqual(
            set(self.vistas),
            {"v_lista_matriculados", "v_detalle_asistencia", "v_resumen_asistencia"},
        )


class ColumnasAnadidasDespues(SimpleTestCase):
    """
    Cada columna que se añade con ALTER está también en el CREATE TABLE.

    Hacen falta las dos: el ALTER pone la columna en las bases que ya
    existen, y el CREATE la pone en las instalaciones nuevas. Si se escribe
    solo el ALTER, quien instale de cero se queda sin ella y la pantalla
    falla en su primer arranque; si se escribe solo el CREATE, la que ya
    está instalada no la recibe nunca.
    """

    def setUp(self):
        _, self.sql = leer()
        self.tablas = tablas_del_script(self.sql)

    def alteraciones(self):
        return re.findall(
            r"ALTER TABLE (\w+) ADD COLUMN (\w+)", self.sql
        )

    def test_hay_al_menos_una(self):
        # Si algún día no queda ninguna, esta clase sobra y se borra.
        self.assertTrue(self.alteraciones())

    def test_cada_una_esta_tambien_en_la_creacion_de_la_tabla(self):
        for tabla, columna in self.alteraciones():
            with self.subTest(tabla=tabla, columna=columna):
                self.assertIn(columna, self.tablas.get(tabla, set()))

    def test_se_comprueba_antes_de_anadirla(self):
        # Sin la comprobación, reimportar el instalador daría error 1060
        # («Duplicate column name») y cortaría el resto del archivo.
        for _, columna in self.alteraciones():
            with self.subTest(columna=columna):
                self.assertIn(f"AND COLUMN_NAME  = '{columna}'", self.sql)


class RutinasQueLlamaLaAplicacion(SimpleTestCase):
    def setUp(self):
        _, self.sql = leer()

    def test_los_tres_procedimientos_estan_definidos(self):
        # services.py los invoca por nombre con callproc(); si falta uno, el
        # llamado de asistencia deja de funcionar entero.
        for rutina in ("sp_iniciar_sesion", "sp_marcar_asistencia", "sp_cerrar_sesion"):
            with self.subTest(rutina=rutina):
                self.assertIn(f"CREATE PROCEDURE {rutina}", self.sql)

    def test_los_dos_triggers_estan_definidos(self):
        for disparador in ("trg_asistencia_valida_grupo", "trg_asistencia_sesion_cerrada"):
            with self.subTest(trigger=disparador):
                self.assertIn(f"CREATE TRIGGER {disparador}", self.sql)

    def test_sp_iniciar_sesion_recibe_los_seis_parametros(self):
        # services.callproc envía 6 valores y lee el OUT en la posición 5.
        # Hasta el paréntesis que va solo en su línea: si se corta en el
        # primero, VARCHAR(255) deja fuera al último parámetro.
        cuerpo = re.search(
            r"CREATE PROCEDURE sp_iniciar_sesion\((.*?)\n\)", self.sql, re.S
        ).group(1)
        self.assertEqual(len(re.findall(r"\b(?:IN|OUT)\s+p_", cuerpo)), 6)
        self.assertIn("OUT p_id_sesion", cuerpo)

    def test_solo_los_matriculados_activos_entran_en_la_lista(self):
        self.assertIn("m.estado = 'ACTIVA'", self.sql)


class SeguroDeEjecutarDosVeces(SimpleTestCase):
    """Reimportar no puede borrar la asistencia ya registrada."""

    def setUp(self):
        _, sql = leer()
        self.sql = sql
        self.ejecutable = sin_comentarios(sql)

    def test_no_borra_la_base_ni_las_tablas(self):
        self.assertNotIn("DROP DATABASE", self.ejecutable)
        self.assertNotIn("DROP TABLE", self.ejecutable)
        self.assertNotIn("TRUNCATE", self.ejecutable)

    def test_las_tablas_se_crean_solo_si_faltan(self):
        self.assertEqual(
            self.sql.count("CREATE TABLE"), self.sql.count("CREATE TABLE IF NOT EXISTS")
        )

    def test_triggers_y_procedimientos_se_reemplazan_sin_error(self):
        self.assertEqual(self.sql.count("CREATE TRIGGER"), self.sql.count("DROP TRIGGER IF EXISTS"))
        self.assertEqual(self.sql.count("CREATE PROCEDURE"), self.sql.count("DROP PROCEDURE IF EXISTS"))

    def test_los_delimitadores_estan_emparejados(self):
        self.assertEqual(self.sql.count("DELIMITER $$"), self.sql.count("DELIMITER ;"))

    def test_los_datos_iniciales_no_se_duplican(self):
        semilla = self.ejecutable[self.ejecutable.index("INSERT IGNORE INTO facultad"):]
        self.assertNotIn("INSERT INTO", semilla.replace("INSERT IGNORE INTO", ""))


class DatosIniciales(SimpleTestCase):
    def setUp(self):
        _, self.sql = leer()

    def test_trae_los_veintiocho_estudiantes_sin_codigos_repetidos(self):
        bloque = re.search(r"INSERT IGNORE INTO estudiante.*?;", self.sql, re.S).group(0)
        codigos = re.findall(r"'(\d{6})'", bloque)
        self.assertEqual(len(codigos), 28)
        self.assertEqual(len(set(codigos)), 28)

    def test_las_claves_son_hashes_de_django_y_funcionan(self):
        # Si alguien pega un hash a mano, nadie podría entrar; se comprueba
        # que las dos cuentas abran con la contraseña que dice el LEEME.
        hashes = dict(re.findall(r"'(ralvarez|admin)',\s*'(pbkdf2_sha256\$[^']+)'", self.sql))
        self.assertEqual(set(hashes), {"ralvarez", "admin"})
        self.assertTrue(check_password("Asistencia2026", hashes["ralvarez"]))
        self.assertTrue(check_password("AdminUnap2026", hashes["admin"]))

    def test_no_hay_ninguna_clave_en_texto_plano(self):
        self.assertNotIn("Asistencia2026'", self.sql)
        self.assertNotIn("AdminUnap2026'", self.sql)
