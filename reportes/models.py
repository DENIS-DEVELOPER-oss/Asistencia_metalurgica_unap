"""Vista `v_resumen_asistencia` (solo lectura)."""
from django.db import models


class VistaResumenAsistencia(models.Model):
    """
    Resumen por estudiante y grupo.

    La vista agrupa por matrícula, por lo que `codigo_estudiante` es único
    dentro de un mismo `id_grupo`; se usa como clave primaria del modelo y
    las consultas siempre filtran por grupo.
    """

    codigo_estudiante = models.CharField(
        max_length=10, primary_key=True, db_column="codigo_estudiante"
    )
    id_grupo = models.IntegerField(db_column="id_grupo")
    periodo = models.CharField(max_length=10, db_column="periodo")
    codigo_curso = models.CharField(max_length=15, db_column="codigo_curso")
    curso = models.CharField(max_length=150, db_column="curso")
    grupo = models.CharField(max_length=20, db_column="grupo")
    docente = models.CharField(max_length=201, db_column="docente")
    estudiante = models.CharField(max_length=221, db_column="estudiante")
    total_sesiones = models.IntegerField(db_column="total_sesiones")
    presentes = models.IntegerField(null=True, db_column="presentes")
    faltas = models.IntegerField(null=True, db_column="faltas")
    porcentaje_asistencia = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, db_column="porcentaje_asistencia"
    )

    class Meta:
        managed = False
        db_table = "v_resumen_asistencia"
        ordering = ["estudiante"]

    def __str__(self):
        return f"{self.estudiante} · {self.porcentaje_asistencia}%"
