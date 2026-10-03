"""
Estructura académica: facultad, escuela, periodo, curso, grupo, estudiante,
matrícula y la vista v_lista_matriculados.

Todas las tablas existen en `asistencia_unap`: managed = False.
"""
from django.db import models

from cuentas.models import Docente

# El reporte oficial imprime el semestre en letras ("SEMESTRE: PRIMERO").
ORDINALES_SEMESTRE = {
    1: "PRIMERO",
    2: "SEGUNDO",
    3: "TERCERO",
    4: "CUARTO",
    5: "QUINTO",
    6: "SEXTO",
    7: "SÉPTIMO",
    8: "OCTAVO",
    9: "NOVENO",
    10: "DÉCIMO",
}


class Facultad(models.Model):
    id_facultad = models.AutoField(primary_key=True, db_column="id_facultad")
    nombre = models.CharField(max_length=150, unique=True, db_column="nombre")

    class Meta:
        managed = False
        db_table = "facultad"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class EscuelaProfesional(models.Model):
    id_escuela = models.AutoField(primary_key=True, db_column="id_escuela")
    facultad = models.ForeignKey(
        Facultad, on_delete=models.DO_NOTHING, db_column="id_facultad",
        related_name="escuelas",
    )
    nombre = models.CharField(max_length=150, db_column="nombre")

    class Meta:
        managed = False
        db_table = "escuela_profesional"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class PeriodoAcademico(models.Model):
    id_periodo = models.AutoField(primary_key=True, db_column="id_periodo")
    codigo = models.CharField(max_length=10, unique=True, db_column="codigo")
    fecha_inicio = models.DateField(null=True, blank=True, db_column="fecha_inicio")
    fecha_fin = models.DateField(null=True, blank=True, db_column="fecha_fin")
    activo = models.BooleanField(default=True, db_column="activo")

    class Meta:
        managed = False
        db_table = "periodo_academico"
        ordering = ["-codigo"]

    def __str__(self):
        return self.codigo


class Estudiante(models.Model):
    id_estudiante = models.AutoField(primary_key=True, db_column="id_estudiante")
    codigo = models.CharField(max_length=10, unique=True, db_column="codigo")
    apellido_paterno = models.CharField(max_length=60, db_column="apellido_paterno")
    apellido_materno = models.CharField(max_length=60, db_column="apellido_materno")
    nombres = models.CharField(max_length=100, db_column="nombres")
    escuela = models.ForeignKey(
        EscuelaProfesional, on_delete=models.DO_NOTHING, db_column="id_escuela",
        related_name="estudiantes",
    )
    email = models.EmailField(max_length=120, null=True, blank=True, db_column="email")
    activo = models.BooleanField(default=True, db_column="activo")

    class Meta:
        managed = False
        db_table = "estudiante"
        ordering = ["apellido_paterno", "apellido_materno", "nombres"]

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        return f"{self.apellido_paterno} {self.apellido_materno} {self.nombres}".strip()


class Curso(models.Model):
    id_curso = models.AutoField(primary_key=True, db_column="id_curso")
    escuela = models.ForeignKey(
        EscuelaProfesional, on_delete=models.DO_NOTHING, db_column="id_escuela",
        related_name="cursos",
    )
    codigo = models.CharField(max_length=15, db_column="codigo")
    nombre = models.CharField(max_length=150, db_column="nombre")
    creditos = models.DecimalField(max_digits=4, decimal_places=2, db_column="creditos")
    semestre = models.PositiveSmallIntegerField(db_column="semestre")

    class Meta:
        managed = False
        db_table = "curso"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    @property
    def semestre_texto(self):
        return ORDINALES_SEMESTRE.get(self.semestre, str(self.semestre))


class Grupo(models.Model):
    id_grupo = models.AutoField(primary_key=True, db_column="id_grupo")
    curso = models.ForeignKey(
        Curso, on_delete=models.DO_NOTHING, db_column="id_curso", related_name="grupos"
    )
    periodo = models.ForeignKey(
        PeriodoAcademico, on_delete=models.DO_NOTHING, db_column="id_periodo",
        related_name="grupos",
    )
    docente = models.ForeignKey(
        Docente, on_delete=models.DO_NOTHING, db_column="id_docente",
        related_name="grupos",
    )
    nombre = models.CharField(max_length=20, db_column="nombre")

    class Meta:
        managed = False
        db_table = "grupo"
        ordering = ["-periodo__codigo", "curso__codigo", "nombre"]

    def __str__(self):
        return f"{self.curso.codigo} - {self.nombre}"

    @property
    def etiqueta_archivo(self):
        """Fragmento usable en nombres de archivo: MET201_GrupoB_2026-II."""
        grupo = self.nombre.title().replace(" ", "")
        return f"{self.curso.codigo}_{grupo}_{self.periodo.codigo}"


class Matricula(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = "ACTIVA", "Activa"
        RETIRADA = "RETIRADA", "Retirada"

    id_matricula = models.AutoField(primary_key=True, db_column="id_matricula")
    grupo = models.ForeignKey(
        Grupo, on_delete=models.DO_NOTHING, db_column="id_grupo",
        related_name="matriculas",
    )
    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.DO_NOTHING, db_column="id_estudiante",
        related_name="matriculas",
    )
    intento = models.PositiveSmallIntegerField(default=1, db_column="intento")
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.ACTIVA, db_column="estado"
    )
    fecha_matricula = models.DateField(null=True, blank=True, db_column="fecha_matricula")

    class Meta:
        managed = False
        db_table = "matricula"
        ordering = [
            "estudiante__apellido_paterno",
            "estudiante__apellido_materno",
            "estudiante__nombres",
        ]

    def __str__(self):
        return f"{self.estudiante} / {self.grupo}"


class VistaListaMatriculados(models.Model):
    """Vista `v_lista_matriculados` (solo lectura)."""

    id_matricula = models.IntegerField(primary_key=True, db_column="id_matricula")
    id_grupo = models.IntegerField(db_column="id_grupo")
    periodo = models.CharField(max_length=10, db_column="periodo")
    codigo_curso = models.CharField(max_length=15, db_column="codigo_curso")
    curso = models.CharField(max_length=150, db_column="curso")
    grupo = models.CharField(max_length=20, db_column="grupo")
    docente = models.CharField(max_length=201, db_column="docente")
    codigo_estudiante = models.CharField(max_length=10, db_column="codigo_estudiante")
    estudiante = models.CharField(max_length=221, db_column="estudiante")
    intento = models.PositiveSmallIntegerField(db_column="intento")
    estado_matricula = models.CharField(max_length=10, db_column="estado_matricula")

    class Meta:
        managed = False
        db_table = "v_lista_matriculados"
        ordering = ["estudiante"]

    def __str__(self):
        return self.estudiante
