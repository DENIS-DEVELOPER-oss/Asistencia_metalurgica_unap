"""
Juego de datos para probar el sistema de punta a punta.

Crea dos docentes más (uno con curso propio y otro sin ningún grupo), un
curso con diez alumnos y seis clases ya dictadas con asistencia variada.
Con eso se pueden comprobar las cosas que con un solo curso vacío no se ven:

- que un docente solo alcanza SUS grupos y no los de otro,
- que el administrador consulta todo pero no puede llamar asistencia,
- el reporte con alumnos en riesgo, la matriz alumno x fecha y las
  exportaciones con datos reales,
- el consolidado en Excel con varios docentes a la vez,
- un alumno matriculado a mitad de ciclo (casillas vacías en la matriz),
- el estado vacío de un docente sin cursos.

Uso:
    python manage.py datos_de_prueba
    python manage.py datos_de_prueba --quitar

Todo lo que crea lleva marca propia (usuarios y códigos de la lista de
abajo), así que `--quitar` lo borra sin tocar tus datos reales.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import Curso, EscuelaProfesional, Grupo, Matricula, PeriodoAcademico
from asistencia.models import Asistencia, SesionClase
from asistencia.services import (
    cerrar_sesion_clase,
    iniciar_sesion_clase,
    marcar_asistencia_en_lote,
)
from cuentas.models import Docente, Usuario

CLAVE = "Docente2026"

# ---------------------------------------------------------------- marcadores
USUARIOS = ["jmamani", "lcondori"]
CODIGO_CURSO = "MET305"
CODIGOS_ALUMNO = [f"9000{n:02d}" for n in range(1, 11)]

DOCENTES = [
    # usuario, apellidos, nombres, dni, con_curso
    ("jmamani", "MAMANI QUISPE", "JOSE LUIS", "40111222", True),
    ("lcondori", "CONDORI FLORES", "LUZ MARINA", "40333444", False),
]

ALUMNOS = [
    ("900001", "AGUILAR", "ROJAS", "MARCO ANTONIO"),
    ("900002", "BAUTISTA", "PARI", "SOFIA NICOL"),
    ("900003", "CALSIN", "TURPO", "DIEGO ARMANDO"),
    ("900004", "CHAMBILLA", "ARO", "NOEMI ROSARIO"),
    ("900005", "HUANCA", "TICONA", "CESAR AUGUSTO"),
    ("900006", "LUQUE", "CALCINA", "GABRIELA PAZ"),
    ("900007", "MENDOZA", "SALAS", "IVAN RODRIGO"),
    ("900008", "PACOMPIA", "ZAPANA", "ROSA ELENA"),
    ("900009", "TITO", "CUTIPA", "ALVARO JESUS"),
    # El décimo se matricula a mitad de ciclo, a propósito.
    ("900010", "VARGAS", "PINTO", "CAMILA ANDREA"),
]

# Asistencia de cada clase, alumno por alumno (en el orden de ALUMNOS).
# Pensada para que el reporte tenga de todo: alumnos al 100 %, alumnos
# con alguna falta y dos por encima del 30 % de faltas.
CLASES = [
    ("Introducción a las operaciones unitarias", "PPPPPPFPP"),
    ("Balance de materia",                       "PPPPPFFPP"),
    ("Molienda y clasificación",                 "PPPPFFFPP"),
    ("Flotación: fundamentos",                   "PPPPPFFPP" "P"),
    ("Espesamiento y filtración",                "PPPPPFFPP" "P"),
    ("Práctica de laboratorio",                  "PPPPPFFPP" "P"),
]

LETRA = {"P": "PRESENTE", "F": "FALTA"}


class Command(BaseCommand):
    help = "Crea o quita un juego de datos para probar el sistema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quitar",
            action="store_true",
            help="Borra todo lo que creó este comando y no toca nada más.",
        )

    def handle(self, *args, **opciones):
        if opciones["quitar"]:
            self.quitar()
        else:
            self.crear()

    # ------------------------------------------------------------- crear
    def crear(self):
        escuela = EscuelaProfesional.objects.order_by("id_escuela").first()
        if escuela is None:
            self.stderr.write("No hay ninguna escuela profesional en la base.")
            return
        periodo = (
            PeriodoAcademico.objects.filter(activo=True).order_by("-codigo").first()
            or PeriodoAcademico.objects.order_by("-codigo").first()
        )
        if periodo is None:
            self.stderr.write("No hay ningún periodo académico en la base.")
            return

        with transaction.atomic():
            fichas = {}
            for usuario, apellidos, nombres, dni, _ in DOCENTES:
                cuenta = Usuario.objects.filter(username=usuario).first()
                if cuenta is None:
                    cuenta = Usuario(username=usuario, rol=Usuario.Rol.DOCENTE, is_active=True)
                cuenta.set_password(CLAVE)
                cuenta.save()

                ficha = Docente.objects.filter(usuario=cuenta).first()
                if ficha is None:
                    ficha = Docente.objects.create(
                        usuario=cuenta, apellidos=apellidos, nombres=nombres,
                        dni=dni, activo=True,
                    )
                fichas[usuario] = ficha
                self.stdout.write(f"  docente  {usuario:10} {apellidos} {nombres}")

            curso = Curso.objects.filter(escuela=escuela, codigo=CODIGO_CURSO).first()
            if curso is None:
                curso = Curso.objects.create(
                    escuela=escuela, codigo=CODIGO_CURSO,
                    nombre="OPERACIONES UNITARIAS", creditos=4, semestre=5,
                )
            grupo = Grupo.objects.filter(curso=curso, periodo=periodo, nombre="GRUPO A").first()
            if grupo is None:
                grupo = Grupo.objects.create(
                    curso=curso, periodo=periodo,
                    docente=fichas["jmamani"], nombre="GRUPO A",
                )
            self.stdout.write(f"  curso    {curso.codigo} · {grupo.nombre} -> {grupo.docente}")

            estudiantes = {}
            for codigo, paterno, materno, nombres in ALUMNOS:
                from academico.models import Estudiante

                alumno = Estudiante.objects.filter(codigo=codigo).first()
                if alumno is None:
                    alumno = Estudiante.objects.create(
                        codigo=codigo, apellido_paterno=paterno,
                        apellido_materno=materno, nombres=nombres,
                        escuela=escuela, activo=True,
                    )
                estudiantes[codigo] = alumno

            hoy = date.today()

            def matricular(codigo):
                Matricula.objects.get_or_create(
                    grupo=grupo, estudiante=estudiantes[codigo],
                    defaults={"intento": 1, "estado": Matricula.Estado.ACTIVA,
                              "fecha_matricula": hoy},
                )

            # Los nueve primeros desde el inicio; el décimo, más adelante.
            for codigo in CODIGOS_ALUMNO[:9]:
                matricular(codigo)
            self.stdout.write("  alumnos  9 matriculados al empezar el ciclo")

        # Las clases se crean fuera del atomic: los procedimientos de la base
        # abren su propia transacción.
        if SesionClase.objects.filter(grupo=grupo).exists():
            self.stdout.write(self.style.WARNING("  clases   ya existían, no se repiten"))
        else:
            self._dictar_clases(grupo, estudiantes, matricular)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Datos de prueba listos."))
        self.stdout.write(f"  Docentes nuevos: {', '.join(USUARIOS)}  ·  contraseña: {CLAVE}")
        self.stdout.write("  Para quitarlos:  python manage.py datos_de_prueba --quitar")

    def _dictar_clases(self, grupo, estudiantes, matricular):
        """Seis clases reales, pasando por los procedimientos almacenados."""
        primera = date.today() - timedelta(days=21)

        for numero, (tema, patron) in enumerate(CLASES, start=1):
            # El décimo alumno entra al curso antes de la cuarta clase.
            if numero == 4:
                matricular(CODIGOS_ALUMNO[9])
                self.stdout.write("  alumnos  el 10.º se matricula antes de la 4.ª clase")

            fecha = primera + timedelta(days=(numero - 1) * 3)
            id_sesion = iniciar_sesion_clase(
                id_grupo=grupo.id_grupo,
                id_docente=grupo.docente_id,
                fecha=fecha.isoformat(),
                hora_inicio="08:00",
                tema=tema,
            )

            # `sp_iniciar_sesion` ya creó la lista: se marca sobre ella.
            por_codigo = {
                a.matricula.estudiante.codigo: a.matricula_id
                for a in Asistencia.objects.filter(
                    sesion_id=id_sesion
                ).select_related("matricula__estudiante")
            }
            marcas = []
            for indice, letra in enumerate(patron):
                codigo = CODIGOS_ALUMNO[indice]
                if codigo in por_codigo:
                    marcas.append({"id_matricula": por_codigo[codigo], "estado": LETRA[letra]})
            if marcas:
                marcar_asistencia_en_lote(id_sesion, marcas)

            # La última se deja abierta, para ver la pantalla «en curso».
            if numero < len(CLASES):
                cerrar_sesion_clase(id_sesion)

        self.stdout.write(
            f"  clases   {len(CLASES)} dictadas "
            f"({len(CLASES) - 1} cerradas y la última abierta)"
        )

    # ------------------------------------------------------------ quitar
    def quitar(self):
        from academico.models import Estudiante

        with transaction.atomic():
            grupos = Grupo.objects.filter(curso__codigo=CODIGO_CURSO)
            sesiones = SesionClase.objects.filter(grupo__in=grupos)
            Asistencia.objects.filter(sesion__in=sesiones).delete()
            borradas = sesiones.count()
            sesiones.delete()

            Matricula.objects.filter(estudiante__codigo__in=CODIGOS_ALUMNO).delete()
            grupos.delete()
            Curso.objects.filter(codigo=CODIGO_CURSO).delete()
            Estudiante.objects.filter(codigo__in=CODIGOS_ALUMNO).delete()

            Docente.objects.filter(usuario__username__in=USUARIOS).delete()
            Usuario.objects.filter(username__in=USUARIOS).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Datos de prueba eliminados ({borradas} clases, "
                f"{len(CODIGOS_ALUMNO)} alumnos, {len(USUARIOS)} docentes)."
            )
        )
