"""
Reportes de mentira con la misma forma que devuelve `reportes.datos`.

Sirven para probar las tres exportaciones sin tocar MySQL: los generadores
reciben un diccionario, no modelos, así que se les puede dar este.
"""
import datetime


def cabecera():
    return {
        "id_grupo": 1,
        "universidad": "UNIVERSIDAD NACIONAL DEL ALTIPLANO PUNO",
        "facultad": "INGENIERIA GEOLOGICA Y METALURGICA",
        "escuela": "INGENIERIA METALURGICA",
        "codigo_curso": "MET201",
        "curso": "METALURGIA GENERAL",
        "creditos": "3.00",
        "semestre": 3,
        "semestre_texto": "TERCERO",
        "grupo": "GRUPO B",
        "periodo": "2026-II",
        "docente": "ALVAREZ ROJAS ROSA MARIA",
    }


def reporte_de_grupo(total_sesiones=5):
    """Reporte completo de un grupo, con un alumno en riesgo y otro tardío."""
    sesiones = [
        {
            "id_sesion": numero,
            "fecha": datetime.date(2026, 4, numero),
            "hora_inicio": datetime.time(8, 0),
            "tema": f"Tema de la clase {numero}",
            "estado": "CERRADA",
            "etiqueta": datetime.date(2026, 4, numero).strftime("%d/%m"),
        }
        for numero in range(1, total_sesiones + 1)
    ]
    ids = [s["id_sesion"] for s in sesiones]

    def alumno(numero, codigo, nombre, letras, semaforo, en_riesgo):
        # Menos letras que sesiones = alumno matriculado a mitad de ciclo.
        marcas = {id_sesion: letra for id_sesion, letra in zip(ids[-len(letras):], letras)}
        celdas = [marcas.get(id_sesion, "") for id_sesion in ids]
        cuenta = {letra: letras.count(letra) for letra in "PF"}
        total = len(letras)
        asistio = cuenta["P"]
        return {
            "numero": numero,
            "codigo": codigo,
            "nombre": nombre,
            "total_sesiones": total,
            "presentes": cuenta["P"],
            "faltas": cuenta["F"],
            "porcentaje_asistencia": round(100 * asistio / total, 2) if total else None,
            "porcentaje_faltas": round(100 * cuenta["F"] / total, 2) if total else None,
            "en_riesgo": en_riesgo,
            "semaforo": semaforo,
            "marcas": marcas,
            "celdas": celdas,
        }

    alumnos = [
        alumno(1, "266197", "QUISPE MAMANI JUAN CARLOS", list("PPPPP"), "verde", False),
        alumno(2, "266483", "CONDORI APAZA MARIA LUZ", list("FTFPF"), "rojo", True),
        alumno(3, "266473", "FLORES HUANCA ANA", list("PPP"), "verde", False),
    ]

    return {
        "cabecera": cabecera(),
        "fecha_emision": datetime.datetime(2026, 4, 20, 10, 30),
        "sesiones": sesiones,
        "alumnos": alumnos,
        "total_alumnos": len(alumnos),
        "total_sesiones": len(sesiones),
        "porcentaje_promedio": 80.0,
        "total_en_riesgo": 1,
        "umbral_inhabilitacion": 30.0,
        "semaforo": {"verde": 85.0, "ambar": 70.0},
    }


def datos_de_una_sesion():
    """Lo que devuelve `reportes.datos.datos_de_sesion`."""
    alumnos = [
        {"numero": 1, "codigo": "266197", "nombre": "QUISPE MAMANI JUAN CARLOS",
         "estado": "PRESENTE", "letra": "P", "observacion": ""},
        {"numero": 2, "codigo": "266483", "nombre": "CONDORI APAZA MARIA LUZ",
         "estado": "FALTA", "letra": "F", "observacion": "Avisó por teléfono"},
        {"numero": 3, "codigo": "266473", "nombre": "FLORES HUANCA ANA",
         "estado": "PRESENTE", "letra": "P", "observacion": ""},
    ]
    return {
        "cabecera": cabecera(),
        "fecha_emision": datetime.datetime(2026, 4, 20, 10, 30),
        "sesion": {
            "id_sesion": 3,
            "fecha": datetime.date(2026, 4, 3),
            "hora_inicio": datetime.time(8, 0),
            "hora_fin": datetime.time(9, 40),
            "tema": "Tema de la clase 3",
            "estado": "CERRADA",
        },
        "alumnos": alumnos,
        "resumen": {"total": 3, "presentes": 2, "faltas": 1,
                    "porcentaje_asistencia": 66.67},
    }
