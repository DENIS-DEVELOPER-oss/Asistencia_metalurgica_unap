"""
Formatos de fecha y número para Perú.

Django trae el locale «es» con coma como separador decimal, pero en Perú
el separador decimal es el punto. Además, una coma dentro de un
`style="width:..%"` rompería las barras de porcentaje del reporte.
"""
DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = " "
NUMBER_GROUPING = 0

DATE_FORMAT = "d/m/Y"
TIME_FORMAT = "H:i"
DATETIME_FORMAT = "d/m/Y H:i"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
FIRST_DAY_OF_WEEK = 1  # lunes

DATE_INPUT_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
TIME_INPUT_FORMATS = ["%H:%M", "%H:%M:%S"]
DATETIME_INPUT_FORMATS = ["%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"]
