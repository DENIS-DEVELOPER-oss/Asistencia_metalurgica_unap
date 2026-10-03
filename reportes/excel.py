"""
Generación del reporte de asistencia en Excel (openpyxl).

Hoja «Resumen»: encabezado oficial + totales por alumno con semáforo.
Hoja «Detalle»: matriz alumno x fecha con la letra P / T / F / J.
"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

AZUL = "1E3A8A"
DORADO = "D4A017"

FUENTE_TITULO = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
FUENTE_ETIQUETA = Font(name="Calibri", size=10, bold=True)
FUENTE_VALOR = Font(name="Calibri", size=10)
FUENTE_CABECERA_TABLA = Font(name="Calibri", size=10, bold=True, color="FFFFFF")

RELLENO_AZUL = PatternFill("solid", fgColor=AZUL)
RELLENO_DORADO = PatternFill("solid", fgColor=DORADO)
RELLENO_VERDE = PatternFill("solid", fgColor="C6EFCE")
RELLENO_AMBAR = PatternFill("solid", fgColor="FFEB9C")
RELLENO_ROJO = PatternFill("solid", fgColor="FFC7CE")
RELLENO_RIESGO = PatternFill("solid", fgColor="FDE8E8")

FUENTE_VERDE = Font(color="006100", bold=True)
FUENTE_AMBAR = Font(color="9C6500", bold=True)
FUENTE_ROJO = Font(color="9C0006", bold=True)

_linea = Side(style="thin", color="B0B7C3")
BORDE = Border(left=_linea, right=_linea, top=_linea, bottom=_linea)

CENTRO = Alignment(horizontal="center", vertical="center")
IZQUIERDA = Alignment(horizontal="left", vertical="center")


def _escribir_cabecera(hoja, cabecera, ultima_columna, fecha_emision=None):
    """Encabezado institucional en las primeras filas de la hoja."""
    letra_final = get_column_letter(ultima_columna)

    hoja.merge_cells(f"A1:{letra_final}1")
    celda = hoja["A1"]
    celda.value = cabecera["universidad"]
    celda.font = FUENTE_TITULO
    celda.fill = RELLENO_AZUL
    celda.alignment = CENTRO
    hoja.row_dimensions[1].height = 22

    hoja.merge_cells(f"A2:{letra_final}2")
    celda = hoja["A2"]
    celda.value = f"REPORTE DE ASISTENCIA — {cabecera['periodo']}"
    celda.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    celda.fill = RELLENO_DORADO
    celda.alignment = CENTRO
    hoja.row_dimensions[2].height = 18

    datos = [
        ("FACULTAD:", cabecera["facultad"]),
        ("ESCUELA PROFESIONAL:", cabecera["escuela"]),
        ("CURSO:", f"{cabecera['codigo_curso']} - {cabecera['curso']}"),
        ("DOCENTE:", cabecera["docente"]),
        (
            "SEMESTRE:",
            f"{cabecera['semestre_texto']}  -  CRÉDITOS: {cabecera['creditos']}"
            f"  -  GRUPO: {cabecera['grupo']}",
        ),
    ]
    if fecha_emision is not None:
        datos.append(("FECHA DE EMISIÓN:", fecha_emision.strftime("%d/%m/%Y %H:%M")))
    fila = 4
    for etiqueta, valor in datos:
        hoja.cell(row=fila, column=1, value=etiqueta).font = FUENTE_ETIQUETA
        hoja.merge_cells(
            start_row=fila, start_column=2, end_row=fila, end_column=ultima_columna
        )
        celda = hoja.cell(row=fila, column=2, value=valor)
        celda.font = FUENTE_VALOR
        celda.alignment = IZQUIERDA
        fila += 1
    return fila + 1  # una fila en blanco de separación


def _pintar_cabecera_tabla(hoja, fila, titulos):
    for indice, titulo in enumerate(titulos, start=1):
        celda = hoja.cell(row=fila, column=indice, value=titulo)
        celda.font = FUENTE_CABECERA_TABLA
        celda.fill = RELLENO_AZUL
        celda.alignment = CENTRO
        celda.border = BORDE
    hoja.row_dimensions[fila].height = 28


def _pintar_letra(celda, letra):
    """Colorea una celda según la letra del estado de asistencia."""
    if letra == "P":
        celda.fill, celda.font = RELLENO_VERDE, FUENTE_VERDE
    elif letra == "F":
        celda.fill, celda.font = RELLENO_ROJO, FUENTE_ROJO


def _ajustar_columnas(hoja, anchos):
    for indice, ancho in enumerate(anchos, start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = ancho


def _hoja_resumen(libro, reporte):
    hoja = libro.active
    hoja.title = "Resumen"
    cabecera = reporte["cabecera"]

    titulos = [
        "N°",
        "CÓDIGO",
        "APELLIDOS Y NOMBRES",
        "SESIONES",
        "PRESENTES",
        "FALTAS",
        "% ASISTENCIA",
        "ESTADO",
    ]
    fila_titulos = _escribir_cabecera(
        hoja, cabecera, len(titulos), reporte.get("fecha_emision")
    )
    _pintar_cabecera_tabla(hoja, fila_titulos, titulos)

    fila = fila_titulos + 1
    primera_fila_datos = fila
    for alumno in reporte["alumnos"]:
        valores = [
            alumno["numero"],
            alumno["codigo"],
            alumno["nombre"],
            alumno["total_sesiones"],
            alumno["presentes"],
            alumno["faltas"],
            alumno["porcentaje_asistencia"],
            "EN RIESGO" if alumno["en_riesgo"] else "REGULAR",
        ]
        for indice, valor in enumerate(valores, start=1):
            celda = hoja.cell(row=fila, column=indice, value=valor)
            celda.border = BORDE
            celda.alignment = IZQUIERDA if indice == 3 else CENTRO
            if indice == 9 and valor is not None:
                celda.number_format = '0.00"%"'
            if alumno["en_riesgo"] and indice == 10:
                celda.fill = RELLENO_RIESGO
                celda.font = FUENTE_ROJO
        fila += 1
    ultima_fila_datos = fila - 1

    if ultima_fila_datos >= primera_fila_datos:
        rango = f"I{primera_fila_datos}:I{ultima_fila_datos}"
        ancla = f"$I${primera_fila_datos}"
        hoja.conditional_formatting.add(
            rango,
            FormulaRule(
                formula=[f"AND(ISNUMBER({ancla}),{ancla}>=85)"],
                fill=RELLENO_VERDE,
                font=FUENTE_VERDE,
            ),
        )
        hoja.conditional_formatting.add(
            rango,
            FormulaRule(
                formula=[f"AND(ISNUMBER({ancla}),{ancla}>=70,{ancla}<85)"],
                fill=RELLENO_AMBAR,
                font=FUENTE_AMBAR,
            ),
        )
        hoja.conditional_formatting.add(
            rango,
            FormulaRule(
                formula=[f"AND(ISNUMBER({ancla}),{ancla}<70)"],
                fill=RELLENO_ROJO,
                font=FUENTE_ROJO,
            ),
        )
        hoja.auto_filter.ref = f"A{fila_titulos}:J{ultima_fila_datos}"

    # Pie con los parámetros aplicados.
    fila += 1
    hoja.cell(
        row=fila,
        column=1,
        value=(
            f"Semáforo: verde ≥ {reporte['semaforo']['verde']}% · "
            f"ámbar {reporte['semaforo']['ambar']}–{reporte['semaforo']['verde'] - 1}% · "
            f"rojo < {reporte['semaforo']['ambar']}%. "
            f"En riesgo de inhabilitación: más de {reporte['umbral_inhabilitacion']:.0f}% de faltas. "
            "El porcentaje es el de clases a las que asistió."
        ),
    ).font = Font(name="Calibri", size=9, italic=True)
    hoja.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=10)

    _ajustar_columnas(hoja, [6, 12, 42, 10, 12, 10, 14, 12])
    hoja.freeze_panes = hoja.cell(row=primera_fila_datos, column=4)
    return hoja


def _hoja_detalle(libro, reporte):
    hoja = libro.create_sheet("Detalle")
    cabecera = reporte["cabecera"]
    sesiones = reporte["sesiones"]

    titulos = ["N°", "CÓDIGO", "APELLIDOS Y NOMBRES"]
    titulos += [sesion["etiqueta"] for sesion in sesiones]
    titulos += ["PRESENTES", "FALTAS", "% ASIST."]

    fila_titulos = _escribir_cabecera(
        hoja, cabecera, len(titulos), reporte.get("fecha_emision")
    )
    _pintar_cabecera_tabla(hoja, fila_titulos, titulos)

    fila = fila_titulos + 1
    primera_fila_datos = fila
    for alumno in reporte["alumnos"]:
        hoja.cell(row=fila, column=1, value=alumno["numero"]).alignment = CENTRO
        hoja.cell(row=fila, column=2, value=alumno["codigo"]).alignment = CENTRO
        hoja.cell(row=fila, column=3, value=alumno["nombre"]).alignment = IZQUIERDA

        columna = 4
        for sesion in sesiones:
            letra = alumno["marcas"].get(sesion["id_sesion"], "")
            celda = hoja.cell(row=fila, column=columna, value=letra)
            celda.alignment = CENTRO
            _pintar_letra(celda, letra)
            columna += 1

        for valor in (
            alumno["presentes"],
            alumno["faltas"],
        ):
            hoja.cell(row=fila, column=columna, value=valor).alignment = CENTRO
            columna += 1

        celda = hoja.cell(row=fila, column=columna, value=alumno["porcentaje_asistencia"])
        celda.alignment = CENTRO
        if alumno["porcentaje_asistencia"] is not None:
            celda.number_format = '0.00"%"'

        for indice in range(1, len(titulos) + 1):
            hoja.cell(row=fila, column=indice).border = BORDE
        fila += 1

    _ajustar_columnas(hoja, [6, 12, 42] + [6] * len(sesiones) + [12, 10, 12])
    if reporte["alumnos"]:
        hoja.freeze_panes = hoja.cell(row=primera_fila_datos, column=4)
        hoja.auto_filter.ref = (
            f"A{fila_titulos}:{get_column_letter(len(titulos))}{fila - 1}"
        )

    # Leyenda de las fechas con su tema.
    fila += 1
    hoja.cell(row=fila, column=1, value="LEYENDA DE SESIONES").font = FUENTE_ETIQUETA
    fila += 1
    for sesion in sesiones:
        hoja.cell(row=fila, column=1, value=sesion["etiqueta"]).font = FUENTE_VALOR
        hoja.cell(
            row=fila,
            column=2,
            value=(
                f"{sesion['fecha'].strftime('%d/%m/%Y')} "
                f"{sesion['hora_inicio'].strftime('%H:%M')} — "
                f"{sesion['tema'] or 'Sin tema'} ({sesion['estado']})"
            ),
        ).font = FUENTE_VALOR
        fila += 1

    return hoja


def generar_excel(reporte):
    """Reporte de un grupo: hojas «Resumen» y «Detalle»."""
    libro = Workbook()
    _hoja_resumen(libro, reporte)
    _hoja_detalle(libro, reporte)

    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------
# Excel consolidado de todos los cursos del docente
# ---------------------------------------------------------------------
def _nombre_de_hoja(reporte, usados):
    """Nombre de hoja válido en Excel: máx. 31 caracteres y sin repetir."""
    cabecera = reporte["cabecera"]
    grupo = cabecera["grupo"].replace("GRUPO", "G").strip()
    base = f"{cabecera['codigo_curso']} {grupo}"[:31]
    nombre = base
    contador = 2
    while nombre in usados:
        sufijo = f" ({contador})"
        nombre = base[: 31 - len(sufijo)] + sufijo
        contador += 1
    usados.add(nombre)
    return nombre


def _docentes_de(reportes):
    """
    Etiqueta y valor de la linea «DOCENTE» del consolidado.

    Se deduce de los grupos incluidos, no de quien descarga el archivo: un
    administrador ve cursos de varios docentes y no es docente de ninguno.
    """
    nombres = sorted({r["cabecera"]["docente"] for r in reportes})
    if len(nombres) == 1:
        return "DOCENTE:", nombres[0]
    if len(nombres) <= 4:
        return "DOCENTES:", " · ".join(nombres)
    return "DOCENTES:", f"{len(nombres)} docentes (ver la columna DOCENTE)"


def _hoja_general(libro, reportes, generado_por):
    """Hoja con una fila por curso: la vista de conjunto."""
    hoja = libro.active
    hoja.title = "General"

    titulos = ["CURSO", "NOMBRE DEL CURSO", "GRUPO", "PERIODO", "DOCENTE",
               "ALUMNOS", "CLASES", "% PROMEDIO", "EN RIESGO"]
    columnas = {titulo: indice for indice, titulo in enumerate(titulos, start=1)}
    ultima_columna = len(titulos)

    hoja.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ultima_columna)
    celda = hoja["A1"]
    celda.value = "UNIVERSIDAD NACIONAL DEL ALTIPLANO PUNO"
    celda.font = FUENTE_TITULO
    celda.fill = RELLENO_AZUL
    celda.alignment = CENTRO
    hoja.row_dimensions[1].height = 22

    hoja.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ultima_columna)
    celda = hoja["A2"]
    celda.value = "CONSOLIDADO DE ASISTENCIA POR CURSO"
    celda.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    celda.fill = RELLENO_DORADO
    celda.alignment = CENTRO

    datos = [_docentes_de(reportes)]
    if generado_por:
        # Quien descarga el archivo es un dato de trazabilidad, no la firma
        # academica del curso.
        datos.append(("GENERADO POR:", generado_por))
    emision = reportes[0].get("fecha_emision") if reportes else None
    if emision is not None:
        datos.append(("FECHA DE EMISIÓN:", emision.strftime("%d/%m/%Y %H:%M")))

    fila = 4
    for etiqueta, valor in datos:
        hoja.cell(row=fila, column=1, value=etiqueta).font = FUENTE_ETIQUETA
        hoja.merge_cells(
            start_row=fila, start_column=2, end_row=fila, end_column=ultima_columna
        )
        celda = hoja.cell(row=fila, column=2, value=valor)
        celda.font = FUENTE_VALOR
        celda.alignment = IZQUIERDA
        fila += 1

    fila_titulos = fila + 1
    _pintar_cabecera_tabla(hoja, fila_titulos, titulos)

    fila = fila_titulos + 1
    primera = fila
    for reporte in reportes:
        cabecera = reporte["cabecera"]
        valores = [
            cabecera["codigo_curso"],
            cabecera["curso"],
            cabecera["grupo"],
            cabecera["periodo"],
            cabecera["docente"],
            reporte["total_alumnos"],
            reporte["total_sesiones"],
            reporte["porcentaje_promedio"],
            reporte["total_en_riesgo"],
        ]
        for indice, valor in enumerate(valores, start=1):
            celda = hoja.cell(row=fila, column=indice, value=valor)
            celda.border = BORDE
            alineado_a_la_izquierda = indice in (
                columnas["NOMBRE DEL CURSO"], columnas["DOCENTE"]
            )
            celda.alignment = IZQUIERDA if alineado_a_la_izquierda else CENTRO
            if indice == columnas["% PROMEDIO"] and valor is not None:
                celda.number_format = '0.00"%"'
            if indice == columnas["EN RIESGO"] and valor:
                celda.fill = RELLENO_RIESGO
                celda.font = FUENTE_ROJO
        fila += 1
    ultima = fila - 1

    if ultima >= primera:
        letra = get_column_letter(columnas["% PROMEDIO"])
        rango = f"{letra}{primera}:{letra}{ultima}"
        ancla = f"${letra}${primera}"
        for formula, relleno, fuente in (
            (f"AND(ISNUMBER({ancla}),{ancla}>=85)", RELLENO_VERDE, FUENTE_VERDE),
            (f"AND(ISNUMBER({ancla}),{ancla}>=70,{ancla}<85)", RELLENO_AMBAR, FUENTE_AMBAR),
            (f"AND(ISNUMBER({ancla}),{ancla}<70)", RELLENO_ROJO, FUENTE_ROJO),
        ):
            hoja.conditional_formatting.add(
                rango, FormulaRule(formula=[formula], fill=relleno, font=fuente)
            )
        hoja.auto_filter.ref = (
            f"A{fila_titulos}:{get_column_letter(ultima_columna)}{ultima}"
        )

    fila += 1
    total_alumnos = sum(r["total_alumnos"] for r in reportes)
    total_riesgo = sum(r["total_en_riesgo"] for r in reportes)
    hoja.cell(
        row=fila, column=1,
        value=(
            f"{len(reportes)} cursos · {total_alumnos} matrículas · "
            f"{total_riesgo} alumnos en riesgo de inhabilitación. "
            "Cada curso tiene su propia hoja con el detalle."
        ),
    ).font = Font(name="Calibri", size=9, italic=True)
    hoja.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=ultima_columna)

    _ajustar_columnas(hoja, [12, 40, 14, 11, 32, 10, 9, 13, 11])
    hoja.freeze_panes = hoja.cell(row=primera, column=1)


def _hoja_curso(libro, reporte, nombre_hoja):
    """Una hoja por curso: totales + matriz alumno x fecha."""
    hoja = libro.create_sheet(nombre_hoja)
    sesiones = reporte["sesiones"]

    titulos = ["N°", "CÓDIGO", "APELLIDOS Y NOMBRES"]
    titulos += [s["etiqueta"] for s in sesiones]
    titulos += ["PRESENTES", "FALTAS", "% ASIST."]

    fila_titulos = _escribir_cabecera(
        hoja, reporte["cabecera"], len(titulos), reporte.get("fecha_emision")
    )
    _pintar_cabecera_tabla(hoja, fila_titulos, titulos)

    fila = fila_titulos + 1
    primera = fila
    for alumno in reporte["alumnos"]:
        hoja.cell(row=fila, column=1, value=alumno["numero"]).alignment = CENTRO
        hoja.cell(row=fila, column=2, value=alumno["codigo"]).alignment = CENTRO
        hoja.cell(row=fila, column=3, value=alumno["nombre"]).alignment = IZQUIERDA

        columna = 4
        for sesion in sesiones:
            letra = alumno["marcas"].get(sesion["id_sesion"], "")
            celda = hoja.cell(row=fila, column=columna, value=letra)
            celda.alignment = CENTRO
            _pintar_letra(celda, letra)
            columna += 1

        for valor in (alumno["presentes"], alumno["faltas"]):
            hoja.cell(row=fila, column=columna, value=valor).alignment = CENTRO
            columna += 1

        celda = hoja.cell(row=fila, column=columna, value=alumno["porcentaje_asistencia"])
        celda.alignment = CENTRO
        if alumno["porcentaje_asistencia"] is not None:
            celda.number_format = '0.00"%"'
        if alumno["en_riesgo"]:
            celda.fill = RELLENO_ROJO
            celda.font = FUENTE_ROJO

        for indice in range(1, len(titulos) + 1):
            hoja.cell(row=fila, column=indice).border = BORDE
        fila += 1

    _ajustar_columnas(hoja, [6, 12, 42] + [6] * len(sesiones) + [12, 10, 12])
    if reporte["alumnos"]:
        hoja.freeze_panes = hoja.cell(row=primera, column=4)


def generar_excel_general(reportes, generado_por=""):
    """
    Consolidado de varios cursos.

    Hoja «General» con una fila por curso y, después, una hoja por curso
    con la matriz alumno x fecha. `generado_por` es quien descarga el
    archivo; el docente de cada curso sale de los datos del grupo.
    """
    libro = Workbook()
    _hoja_general(libro, reportes, generado_por)

    usados = set()
    for reporte in reportes:
        _hoja_curso(libro, reporte, _nombre_de_hoja(reporte, usados))

    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------
# Excel de una sola clase
# ---------------------------------------------------------------------
def generar_excel_sesion(datos):
    """Lista de asistencia de una clase, con su resumen."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Asistencia"

    cabecera = datos["cabecera"]
    sesion = datos["sesion"]
    resumen = datos["resumen"]

    titulos = ["N°", "CÓDIGO", "APELLIDOS Y NOMBRES", "ESTADO", "OBSERVACIÓN"]
    fila = _escribir_cabecera(hoja, cabecera, len(titulos), datos.get("fecha_emision"))

    hora_fin = sesion["hora_fin"].strftime("%H:%M") if sesion["hora_fin"] else "—"
    detalle = [
        ("CLASE:", f"{sesion['fecha']:%d/%m/%Y}  ·  "
                   f"{sesion['hora_inicio']:%H:%M} a {hora_fin}  ·  {sesion['estado']}"),
        ("TEMA:", sesion["tema"] or "Sin tema registrado"),
        ("RESUMEN:", f"Presentes: {resumen['presentes']}  ·  "
                     f"Faltas: {resumen['faltas']}  ·  Total: {resumen['total']}"),
    ]
    for etiqueta, valor in detalle:
        hoja.cell(row=fila, column=1, value=etiqueta).font = FUENTE_ETIQUETA
        hoja.merge_cells(start_row=fila, start_column=2, end_row=fila, end_column=len(titulos))
        celda = hoja.cell(row=fila, column=2, value=valor)
        celda.font = FUENTE_VALOR
        celda.alignment = IZQUIERDA
        fila += 1

    fila += 1
    fila_titulos = fila
    _pintar_cabecera_tabla(hoja, fila_titulos, titulos)

    fila += 1
    primera = fila
    for alumno in datos["alumnos"]:
        valores = [
            alumno["numero"], alumno["codigo"], alumno["nombre"],
            alumno["estado"], alumno["observacion"],
        ]
        for indice, valor in enumerate(valores, start=1):
            celda = hoja.cell(row=fila, column=indice, value=valor)
            celda.border = BORDE
            celda.alignment = CENTRO if indice in (1, 2, 4) else IZQUIERDA
        _pintar_letra(hoja.cell(row=fila, column=4), alumno["letra"])
        fila += 1

    if datos["alumnos"]:
        hoja.auto_filter.ref = f"A{fila_titulos}:E{fila - 1}"
        hoja.freeze_panes = hoja.cell(row=primera, column=1)

    fila += 1
    hoja.cell(
        row=fila, column=1,
        value="Leyenda de la matriz por fechas: P = Presente · F = Falta.",
    ).font = Font(name="Calibri", size=9, italic=True)

    _ajustar_columnas(hoja, [6, 13, 42, 14, 46])

    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
