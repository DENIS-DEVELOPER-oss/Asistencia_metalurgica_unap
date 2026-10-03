"""Sesiones de clase y marcas de asistencia."""
from django.db import models

from academico.models import Grupo, Matricula
from cuentas.models import Docente


class EstadoAsistencia(models.TextChoices):
    PRESENTE = "PRESENTE", "Presente"
    FALTA = "FALTA", "Falta"


# Letra usada en el reporte oficial para cada estado.
LETRA_ESTADO = {
    EstadoAsistencia.PRESENTE: "P",
    EstadoAsistencia.FALTA: "F",
}


class SesionClase(models.Model):
    class Estado(models.TextChoices):
        ABIERTA = "ABIERTA", "Abierta"
        CERRADA = "CERRADA", "Cerrada"

    id_sesion = models.AutoField(primary_key=True, db_column="id_sesion")
    grupo = models.ForeignKey(
        Grupo, on_delete=models.DO_NOTHING, db_column="id_grupo",
        related_name="sesiones",
    )
    docente = models.ForeignKey(
        Docente, on_delete=models.DO_NOTHING, db_column="id_docente",
        related_name="sesiones",
    )
    fecha = models.DateField(db_column="fecha")
    hora_inicio = models.TimeField(db_column="hora_inicio")
    hora_fin = models.TimeField(null=True, blank=True, db_column="hora_fin")
    tema = models.CharField(max_length=255, null=True, blank=True, db_column="tema")
    estado = models.CharField(
        max_length=8, choices=Estado.choices, default=Estado.ABIERTA, db_column="estado"
    )
    creado_en = models.DateTimeField(auto_now_add=True, db_column="creado_en")

    class Meta:
        managed = False
        db_table = "sesion_clase"
        ordering = ["-fecha", "-hora_inicio"]

    def __str__(self):
        return f"{self.grupo_id} · {self.fecha} {self.hora_inicio}"

    @property
    def esta_abierta(self):
        return self.estado == self.Estado.ABIERTA


class Asistencia(models.Model):
    id_asistencia = models.AutoField(primary_key=True, db_column="id_asistencia")
    sesion = models.ForeignKey(
        SesionClase, on_delete=models.DO_NOTHING, db_column="id_sesion",
        related_name="asistencias",
    )
    matricula = models.ForeignKey(
        Matricula, on_delete=models.DO_NOTHING, db_column="id_matricula",
        related_name="asistencias",
    )
    estado = models.CharField(
        max_length=11,
        choices=EstadoAsistencia.choices,
        default=EstadoAsistencia.FALTA,
        db_column="estado",
    )
    observacion = models.CharField(
        max_length=255, null=True, blank=True, db_column="observacion"
    )
    actualizado_en = models.DateTimeField(auto_now=True, db_column="actualizado_en")

    class Meta:
        managed = False
        db_table = "asistencia"
        ordering = ["id_asistencia"]

    def __str__(self):
        return f"{self.matricula_id} -> {self.estado}"

    @property
    def letra(self):
        return LETRA_ESTADO.get(self.estado, "-")
