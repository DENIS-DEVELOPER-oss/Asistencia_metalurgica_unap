"""
Arranca el sistema con un servidor de verdad, no con el de desarrollo.

`manage.py runserver` es de un solo hilo y la propia documentación de
Django avisa de que no debe usarse para atender a gente de verdad: con
tres docentes llamando lista a la vez, las peticiones se encolan.

Aquí se usa Waitress, que es un servidor WSGI en Python puro —no hay nada
que compilar en Windows— y atiende varias peticiones a la vez. Los
archivos estáticos los sirve WhiteNoise desde el propio proceso, de modo
que no hace falta montar un servidor web delante.

    python servidor.py                 escucha en toda la red, puerto 8000
    python servidor.py --puerto 8080   otro puerto
    python servidor.py --solo-local    solo desde esta computadora
"""
import argparse
import os
import socket
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def direcciones_de_red():
    """IPs de esta computadora, para decirle al docente a dónde entrar."""
    try:
        _, _, ips = socket.gethostbyname_ex(socket.gethostname())
        return sorted({ip for ip in ips if not ip.startswith("127.")})
    except OSError:
        return []


def comprobar_estaticos():
    """
    Los estáticos tienen que estar recogidos antes de arrancar.

    Con `CompressedManifestStaticFilesStorage`, si falta el manifiesto la
    aplicación revienta al pintar la primera plantilla, no al arrancar; es
    mejor detectarlo aquí y decir qué hacer.
    """
    manifiesto = BASE / "staticfiles" / "staticfiles.json"
    if manifiesto.exists():
        return True
    print("\n  Faltan los archivos estáticos.")
    print("  Ejecuta primero:\n")
    print("      app\\Scripts\\python.exe manage.py collectstatic --noinput\n")
    return False


def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--puerto", type=int, default=8000)
    analizador.add_argument("--solo-local", action="store_true",
                            help="No aceptar conexiones desde otras computadoras")
    opciones = analizador.parse_args()

    import django
    django.setup()

    from django.conf import settings

    if settings.DEBUG:
        print("\n  AVISO: DEBUG está en True.")
        print("  Para uso real ponlo en False en el archivo .env: con True,")
        print("  cualquier error muestra en pantalla la configuración y la")
        print("  contraseña de la base de datos.\n")
    elif not comprobar_estaticos():
        return 1

    from config.wsgi import application
    from waitress import serve

    host = "127.0.0.1" if opciones.solo_local else "0.0.0.0"

    print("=" * 62)
    print("  ASISTENCIA UNAP")
    print("=" * 62)
    print(f"  Desde esta computadora:  http://localhost:{opciones.puerto}")
    if not opciones.solo_local:
        for ip in direcciones_de_red():
            print(f"  Desde el celular:        http://{ip}:{opciones.puerto}")
        if direcciones_de_red():
            print("\n  Esas IP tienen que estar en ALLOWED_HOSTS, en el .env.")
    print("\n  Para apagar: Ctrl+C o cierra esta ventana.")
    print("=" * 62 + "\n")

    serve(application, host=host, port=opciones.puerto, threads=8,
          ident="Asistencia UNAP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
