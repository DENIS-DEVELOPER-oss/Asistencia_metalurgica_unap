"""
Generación de los PDF de asistencia con ReportLab.

Replica el formato oficial de la Universidad Nacional del Altiplano Puno:
encabezado institucional, datos del curso, tabla de alumnos, pie con fecha
de emisión y «Pág. X/Y», y espacio para la firma del docente.
"""
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as canvas_modulo
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

AZUL = colors.HexColor("#1E3A8A")
DORADO = colors.HexColor("#D4A017")
GRIS_LINEA = colors.HexColor("#B0B7C3")
GRIS_SUAVE = colors.HexColor("#F1F5F9")

COLOR_ESTADO = {
    "P": (colors.HexColor("#DCFCE7"), colors.HexColor("#15803D")),
    "F": (colors.HexColor("#FEE2E2"), colors.HexColor("#B91C1C")),
}

MARGEN = 12 * mm
ALTO_ENCABEZADO = 20 * mm
ALTO_PIE = 14 * mm

_estilos = getSampleStyleSheet()

ESTILO_ETIQUETA = ParagraphStyle(
    "etiqueta", parent=_estilos["Normal"], fontName="Helvetica-Bold", fontSize=8,
    leading=10, textColor=colors.HexColor("#0F172A"),
)
ESTILO_VALOR = ParagraphStyle(
    "valor", parent=_estilos["Normal"], fontName="Helvetica", fontSize=8, leading=10,
)
ESTILO_CELDA = ParagraphStyle(
    "celda", parent=_estilos["Normal"], fontName="Helvetica", fontSize=7, leading=8.5,
)
ESTILO_FIRMA = ParagraphStyle(
    "firma", parent=_estilos["Normal"], fontName="Helvetica", fontSize=8,
    alignment=TA_CENTER,
)
ESTILO_NOTA = ParagraphStyle(
    "nota", parent=_estilos["Normal"], fontName="Helvetica-Oblique", fontSize=7,
    leading=9, textColor=colors.HexColor("#475569"),
)
ESTILO_SUBTITULO = ParagraphStyle(
    "subtitulo", parent=_estilos["Normal"], fontName="Helvetica-Bold", fontSize=9,
    leading=11, textColor=AZUL, spaceBefore=4, spaceAfter=3,
)


class LienzoNumerado(canvas_modulo.Canvas):
    """Canvas de dos pasadas para poder imprimir «Pág. X/Y»."""

    def __init__(self, *args, **kwargs):
        self._cabecera = kwargs.pop("cabecera", {})
        super().__init__(*args, **kwargs)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._dibujar_encabezado()
            self._dibujar_pie(total)
            super().showPage()
        super().save()

    # -- dibujo ---------------------------------------------------------
    def _dibujar_encabezado(self):
        ancho, alto = self._pagesize
        centro = ancho / 2

        self.setFillColor(AZUL)
        self.setFont("Helvetica-Bold", 11)
        self.drawCentredString(
            centro, alto - 11 * mm, "UNIVERSIDAD NACIONAL DEL ALTIPLANO PUNO"
        )

        self.setFillColor(colors.black)
        self.setFont("Helvetica-Bold", 9.5)
        self.drawCentredString(centro, alto - 15.5 * mm, "REPORTE DE ASISTENCIA")

        self.setFillColor(DORADO)
        self.setFont("Helvetica-Bold", 8)
        self.drawRightString(
            ancho - MARGEN,
            alto - 11 * mm,
            f"ESTUDIANTES[{self._cabecera.get('periodo', '')}]",
        )

        self.setFillColor(colors.HexColor("#64748B"))
        self.setFont("Helvetica-Bold", 7)
        self.drawString(MARGEN, alto - 11 * mm, "VICERRECTORADO ACADÉMICO")

        self.setStrokeColor(DORADO)
        self.setLineWidth(1)
        self.line(MARGEN, alto - 17.5 * mm, ancho - MARGEN, alto - 17.5 * mm)

    def _dibujar_pie(self, total_paginas):
        ancho, _alto = self._pagesize

        self.setStrokeColor(GRIS_LINEA)
        self.setLineWidth(0.5)
        self.line(MARGEN, ALTO_PIE - 2 * mm, ancho - MARGEN, ALTO_PIE - 2 * mm)

        self.setFillColor(colors.HexColor("#475569"))
        self.setFont("Helvetica", 7)
        emitido = datetime.now().strftime("%d/%m/%Y %I:%M %p")
        self.drawString(MARGEN, ALTO_PIE - 6 * mm, f"Fecha de emisión: {emitido}")
        self.drawCentredString(
            ancho / 2,
            ALTO_PIE - 6 * mm,
            f"{self._cabecera.get('codigo_curso', '')} · {self._cabecera.get('grupo', '')}",
        )
        self.drawRightString(
            ancho - MARGEN,
            ALTO_PIE - 6 * mm,
            f"Pág. {self._page_number_actual()}/{total_paginas}",
        )

    def _page_number_actual(self):
        return self._pageNumber


def _fabrica_de_lienzo(cabecera):
    def crear(*args, **kwargs):
        kwargs["cabecera"] = cabecera
        return LienzoNumerado(*args, **kwargs)

    return crear


def _bloque_datos_curso(cabecera, ancho_total):
    """Tabla de dos columnas con los datos del curso (como el reporte oficial)."""
    filas = [
        ["FACULTAD:", cabecera["facultad"]],
        ["ESCUELA PROFESIONAL:", cabecera["escuela"]],
        ["CURSO:", f"{cabecera['codigo_curso']} - {cabecera['curso']}"],
        ["DOCENTE:", cabecera["docente"]],
        [
            "SEMESTRE:",
            f"{cabecera['semestre_texto']}  -  CRÉDITOS: {cabecera['creditos']}"
            f"  -  GRUPO: {cabecera['grupo']}  -  PERIODO: {cabecera['periodo']}",
        ],
    ]
    datos = [
        [Paragraph(etiqueta, ESTILO_ETIQUETA), Paragraph(valor, ESTILO_VALOR)]
        for etiqueta, valor in filas
    ]
    tabla = Table(datos, colWidths=[38 * mm, ancho_total - 38 * mm], hAlign="LEFT")
    tabla.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return tabla


def _bloque_firma(nombre_docente):
    """Espacio de firma al final del documento."""
    linea = Table([[""]], colWidths=[70 * mm], rowHeights=[0.4])
    linea.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.7, colors.black)]))
    return KeepTogether(
        [
            Spacer(1, 14 * mm),
            linea,
            Spacer(1, 1.5 * mm),
            Table(
                [[Paragraph(f"{nombre_docente}<br/>Firma del docente", ESTILO_FIRMA)]],
                colWidths=[70 * mm],
                style=TableStyle(
                    [
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ]
                ),
            ),
        ]
    )


def _estilo_base_tabla():
    return [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_SUAVE]),
    ]


def _particionar_sesiones(sesiones, ancho_disponible):
    """
    Reparte las columnas de fecha en bloques que quepan a lo ancho de la hoja.

    Devuelve una lista de (sesiones_del_bloque, ancho_de_cada_columna_fecha).
    """
    ancho_fijo = 10 * mm + 18 * mm + 4 * (7 * mm) + 16 * mm  # N°, código, PTJF, %
    ancho_nombre_min = 52 * mm
    disponible = ancho_disponible - ancho_fijo - ancho_nombre_min

    if not sesiones:
        return [([], 8 * mm)]

    ancho_columna = 8 * mm
    maximo_por_bloque = max(1, int(disponible // ancho_columna))

    bloques = []
    for inicio in range(0, len(sesiones), maximo_por_bloque):
        trozo = sesiones[inicio : inicio + maximo_por_bloque]
        bloques.append((trozo, ancho_columna))
    return bloques


def generar_pdf_reporte(reporte):
    """PDF del reporte consolidado (matriz alumno x fecha)."""
    cabecera = reporte["cabecera"]
    sesiones = reporte["sesiones"]

    # Con muchas fechas el reporte se imprime en horizontal.
    apaisado = len(sesiones) > 8
    tamano = landscape(A4) if apaisado else A4
    ancho_util = tamano[0] - 2 * MARGEN

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=tamano,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=ALTO_ENCABEZADO,
        bottomMargin=ALTO_PIE + 4 * mm,
        title=f"Reporte de asistencia {cabecera['codigo_curso']} {cabecera['grupo']}",
        author="Universidad Nacional del Altiplano Puno",
    )

    elementos = [_bloque_datos_curso(cabecera, ancho_util), Spacer(1, 4 * mm)]

    bloques = _particionar_sesiones(sesiones, ancho_util)
    desplazamiento = 0
    for trozo, ancho_columna in bloques:
        if len(bloques) > 1:
            titulo = (
                f"Fechas {desplazamiento + 1} a {desplazamiento + len(trozo)} "
                f"de {len(sesiones)}"
            )
            elementos.append(Paragraph(titulo, ESTILO_SUBTITULO))
        desplazamiento += len(trozo)

        encabezados = ["N°", "CÓDIGO", "APELLIDOS Y NOMBRES"]
        encabezados += [s["etiqueta"] for s in trozo]
        encabezados += ["PRES.", "FALT.", "% ASIST."]

        anchos = [10 * mm, 18 * mm]
        ancho_nombre = (
            ancho_util
            - (10 * mm + 18 * mm + 4 * (7 * mm) + 16 * mm)
            - len(trozo) * ancho_columna
        )
        anchos.append(max(ancho_nombre, 40 * mm))
        anchos += [ancho_columna] * len(trozo)
        anchos += [7 * mm] * 4 + [16 * mm]

        datos = [encabezados]
        estilo = _estilo_base_tabla()
        estilo.append(("ALIGN", (2, 1), (2, -1), "LEFT"))

        for indice_fila, alumno in enumerate(reporte["alumnos"], start=1):
            fila = [
                str(alumno["numero"]),
                alumno["codigo"],
                Paragraph(alumno["nombre"], ESTILO_CELDA),
            ]
            for indice_col, sesion in enumerate(trozo):
                letra = alumno["marcas"].get(sesion["id_sesion"], "")
                fila.append(letra)
                if letra in COLOR_ESTADO:
                    fondo, texto = COLOR_ESTADO[letra]
                    columna = 3 + indice_col
                    estilo.append(
                        ("BACKGROUND", (columna, indice_fila), (columna, indice_fila), fondo)
                    )
                    estilo.append(
                        ("TEXTCOLOR", (columna, indice_fila), (columna, indice_fila), texto)
                    )
                    estilo.append(
                        (
                            "FONTNAME",
                            (columna, indice_fila),
                            (columna, indice_fila),
                            "Helvetica-Bold",
                        )
                    )
            fila += [
                str(alumno["presentes"]),
                str(alumno["faltas"]),
                "-" if alumno["porcentaje_asistencia"] is None
                else f"{alumno['porcentaje_asistencia']:.2f}%",
            ]
            datos.append(fila)

            if alumno["en_riesgo"]:
                estilo.append(
                    ("TEXTCOLOR", (-1, indice_fila), (-1, indice_fila), colors.HexColor("#B91C1C"))
                )
                estilo.append(
                    ("FONTNAME", (-1, indice_fila), (-1, indice_fila), "Helvetica-Bold")
                )

        tabla = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
        tabla.setStyle(TableStyle(estilo))
        elementos.append(tabla)
        elementos.append(Spacer(1, 4 * mm))

    leyenda = (
        "Leyenda de la matriz por fechas: P = Presente · F = Falta. "
        "El porcentaje es el de clases a las que asistió. "
        f"Se marca en rojo al alumno con más de {reporte['umbral_inhabilitacion']:.0f}% "
        f"de faltas (riesgo de inhabilitación). Alumnos en riesgo: {reporte['total_en_riesgo']} "
        f"de {reporte['total_alumnos']}."
    )
    elementos.append(Paragraph(leyenda, ESTILO_NOTA))

    if sesiones:
        detalle_fechas = " · ".join(
            f"{s['etiqueta']}: {s['tema'] or 'Sin tema'}" for s in sesiones
        )
        elementos.append(Spacer(1, 1.5 * mm))
        elementos.append(Paragraph(f"Sesiones: {detalle_fechas}", ESTILO_NOTA))

    elementos.append(_bloque_firma(cabecera["docente"]))

    documento.build(elementos, canvasmaker=_fabrica_de_lienzo(cabecera))
    return buffer.getvalue()


def generar_pdf_sesion(datos):
    """PDF de la lista de asistencia de una sola clase."""
    cabecera = datos["cabecera"]
    sesion = datos["sesion"]
    resumen = datos["resumen"]

    ancho_util = A4[0] - 2 * MARGEN
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=ALTO_ENCABEZADO,
        bottomMargin=ALTO_PIE + 4 * mm,
        title=(
            f"Asistencia {cabecera['codigo_curso']} {cabecera['grupo']} "
            f"{sesion['fecha']:%d-%m-%Y}"
        ),
        author="Universidad Nacional del Altiplano Puno",
    )

    elementos = [_bloque_datos_curso(cabecera, ancho_util), Spacer(1, 3 * mm)]

    hora_fin = sesion["hora_fin"].strftime("%H:%M") if sesion["hora_fin"] else "—"
    linea_sesion = (
        f"<b>CLASE:</b> {sesion['fecha']:%d/%m/%Y} &nbsp;&nbsp; "
        f"<b>HORA:</b> {sesion['hora_inicio']:%H:%M} a {hora_fin} &nbsp;&nbsp; "
        f"<b>ESTADO:</b> {sesion['estado']}<br/>"
        f"<b>TEMA:</b> {sesion['tema'] or 'Sin tema registrado'}"
    )
    elementos.append(Paragraph(linea_sesion, ESTILO_VALOR))
    elementos.append(Spacer(1, 3 * mm))

    porcentaje = resumen["porcentaje_asistencia"]
    porcentaje_texto = "—" if porcentaje is None else f"{porcentaje:.2f}%"
    resumen_texto = (
        f"Presentes: {resumen['presentes']} &nbsp;·&nbsp; "
        f"Faltas: {resumen['faltas']} &nbsp;·&nbsp; "
        f"Total: {resumen['total']} &nbsp;·&nbsp; "
        f"Asistencia: {porcentaje_texto}"
    )
    elementos.append(Paragraph(resumen_texto, ESTILO_VALOR))
    elementos.append(Spacer(1, 3 * mm))

    encabezados = ["N°", "CÓDIGO", "APELLIDOS Y NOMBRES", "ESTADO", "OBSERVACIÓN"]
    anchos = [10 * mm, 20 * mm, 70 * mm, 20 * mm, ancho_util - 120 * mm]

    filas = [encabezados]
    estilo = _estilo_base_tabla()
    estilo.append(("ALIGN", (2, 1), (2, -1), "LEFT"))
    estilo.append(("ALIGN", (4, 1), (4, -1), "LEFT"))

    for indice, alumno in enumerate(datos["alumnos"], start=1):
        filas.append(
            [
                str(alumno["numero"]),
                alumno["codigo"],
                Paragraph(alumno["nombre"], ESTILO_CELDA),
                alumno["estado"],
                Paragraph(alumno["observacion"], ESTILO_CELDA),
            ]
        )
        if alumno["letra"] in COLOR_ESTADO:
            fondo, texto = COLOR_ESTADO[alumno["letra"]]
            estilo.append(("BACKGROUND", (3, indice), (3, indice), fondo))
            estilo.append(("TEXTCOLOR", (3, indice), (3, indice), texto))
            estilo.append(("FONTNAME", (3, indice), (3, indice), "Helvetica-Bold"))

    tabla = Table(filas, colWidths=anchos, repeatRows=1, hAlign="LEFT")
    tabla.setStyle(TableStyle(estilo))
    elementos.append(tabla)

    elementos.append(Spacer(1, 2 * mm))
    elementos.append(
        Paragraph(
            "Leyenda de la matriz por fechas: P = Presente · F = Falta.",
            ESTILO_NOTA,
        )
    )
    elementos.append(_bloque_firma(cabecera["docente"]))

    documento.build(elementos, canvasmaker=_fabrica_de_lienzo(cabecera))
    return buffer.getvalue()
