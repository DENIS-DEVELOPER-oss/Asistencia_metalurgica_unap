"""
Utilidades compartidas por los comandos que hablan con MySQL de tú a tú.

Los archivos que empiezan por «_» no son comandos: Django los ignora al
buscar en esta carpeta, así que este es el sitio para lo que usan varios.
"""
import os
import pathlib
import secrets
import string

from django.conf import settings

# Donde suele quedar XAMPP. Se recorren varias unidades porque no siempre
# está en C: en esta PC, por ejemplo, está en D:.
CARPETAS_PROBABLES = [
    "{unidad}:/xampp/mysql/bin",
    "{unidad}:/xampp64/mysql/bin",
    "{unidad}:/Program Files/MySQL/MySQL Server 8.0/bin",
    "{unidad}:/Program Files/MariaDB 10.11/bin",
    "{unidad}:/wamp64/bin/mysql",
    "{unidad}:/laragon/bin/mysql",
]
UNIDADES = "CDEFGH"


def buscar_programa(nombre):
    """
    Ruta del programa de MySQL (`mysql.exe`, `mysqldump.exe`) o None.

    Primero se mira el PATH, que es lo normal en Linux y en instalaciones
    que lo configuran; después las carpetas de XAMPP.
    """
    from shutil import which

    encontrado = which(nombre)
    if encontrado:
        return pathlib.Path(encontrado)

    ejecutable = nombre if os.name != "nt" else f"{nombre}.exe"
    for plantilla in CARPETAS_PROBABLES:
        for unidad in UNIDADES:
            carpeta = pathlib.Path(plantilla.format(unidad=unidad))
            candidato = carpeta / ejecutable
            if candidato.is_file():
                return candidato
            # Las instalaciones de WAMP meten la versión en la ruta.
            if carpeta.is_dir():
                for version in sorted(carpeta.glob("*/bin")):
                    if (version / ejecutable).is_file():
                        return version / ejecutable
    return None


def clave_fuerte(largo=28):
    """
    Contraseña para una cuenta que nadie va a escribir a mano.

    Vive en el archivo .env y la lee el programa, así que puede ser tan
    larga e incómoda como convenga: 28 caracteres de este alfabeto no se
    adivinan probando.

    El alfabeto se queda corto a propósito. Fuera las comillas y la barra
    invertida, que se pelean con la línea de comandos; fuera «=», que es
    lo que separa clave y valor en el .env; y fuera «#», que algunos
    lectores de .env toman por el principio de un comentario y cortarían
    la contraseña por la mitad. Lo que se pierde en variedad se recupera
    con el largo.
    """
    alfabeto = string.ascii_letters + string.digits + "-_.+"
    return "".join(secrets.choice(alfabeto) for _ in range(largo))


# ---------------------------------------------------------------------
# El archivo .env
# ---------------------------------------------------------------------
RUTA_ENV = pathlib.Path(settings.BASE_DIR) / ".env"


def escribir_en_env(valores, ruta=None):
    """
    Cambia (o añade) claves del .env dejando intactos comentarios y orden.

    Reescribir el archivo entero perdería las explicaciones que tiene, que
    son justo lo que permite a otra persona entenderlo dentro de un año.
    """
    ruta = pathlib.Path(ruta or RUTA_ENV)
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.is_file() else []
    pendientes = dict(valores)

    salida = []
    for linea in lineas:
        clave = linea.split("=", 1)[0].strip() if "=" in linea else ""
        if clave in pendientes and not linea.lstrip().startswith("#"):
            salida.append(f"{clave}={pendientes.pop(clave)}")
        else:
            salida.append(linea)

    if pendientes:
        if salida and salida[-1].strip():
            salida.append("")
        for clave, valor in pendientes.items():
            salida.append(f"{clave}={valor}")

    ruta.write_text("\n".join(salida) + "\n", encoding="utf-8", newline="\n")
    return ruta
