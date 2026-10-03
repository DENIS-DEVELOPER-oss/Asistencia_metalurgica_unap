"""
Cabeceras de seguridad que Django no pone por su cuenta.

Django ya trae lo básico desde `settings` (nosniff, referrer, X-Frame-
Options, cookies). Falta lo que hay que construir por petición:

- **Content-Security-Policy.** Le dice al navegador de dónde puede cargar
  código. Si algún día un nombre de alumno o una observación escapara sin
  escapar, el `<script>` que trajera no se ejecutaría: solo corre el
  código propio, marcado con el número de un solo uso (*nonce*) de esta
  petición.
- **Permissions-Policy.** Apaga cámara, micrófono y ubicación. El sistema
  no los usa y así nadie puede pedirlos desde esta pestaña.
- **Cache-Control en las pantallas con datos.** En la PC del aula, tras
  cerrar sesión, el botón «atrás» no debe devolver la lista de alumnos.
"""
import secrets

from django.shortcuts import redirect
from django.urls import reverse


class CabecerasDeSeguridad:
    """
    Un nonce nuevo por petición y las cabeceras que dependen de él.

    Va después de la autenticación para que la plantilla pueda leer el
    nonce ya generado, y antes de que la respuesta salga.
    """

    # Las fuentes de Google se cargan desde su CDN; el resto es propio.
    FUENTES_CSS = "https://fonts.googleapis.com"
    FUENTES_ARCHIVO = "https://fonts.gstatic.com"

    PERMISOS = (
        "accelerometer=(), camera=(), display-capture=(), geolocation=(), "
        "gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        respuesta = self.get_response(request)

        respuesta.setdefault("Content-Security-Policy", self.politica(request))
        respuesta.setdefault("Permissions-Policy", self.PERMISOS)

        # Las pantallas privadas no se guardan en el disco del navegador.
        # Sin esto, en una PC compartida basta con pulsar «atrás» después
        # de salir para volver a ver la lista de un curso.
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            respuesta.setdefault(
                "Cache-Control", "no-store, no-cache, must-revalidate, private"
            )

        return respuesta

    def politica(self, request):
        nonce = f"'nonce-{request.csp_nonce}'"
        reglas = [
            "default-src 'self'",
            f"script-src 'self' {nonce}",
            # 'unsafe-inline' en los estilos: las plantillas usan atributos
            # `style=` para los detalles de cada fila. No abre la puerta a
            # ejecutar código, que es lo que importa aquí.
            f"style-src 'self' 'unsafe-inline' {self.FUENTES_CSS}",
            f"font-src 'self' {self.FUENTES_ARCHIVO}",
            "img-src 'self' data:",
            "connect-src 'self'",
            # Los formularios solo pueden enviarse a este mismo sistema.
            "form-action 'self'",
            # Nadie puede meter el sistema dentro de un marco para
            # superponerle botones falsos.
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "object-src 'none'",
        ]
        return "; ".join(reglas)


def nonce_para_plantillas(request):
    """Deja el nonce a mano en las plantillas: `<script nonce="{{ csp_nonce }}">`."""
    return {"csp_nonce": getattr(request, "csp_nonce", "")}


class ClavePendienteDeCambio:
    """
    Quien entra con una clave que le pusieron, elige la suya antes de seguir.

    La clave de reparto de un docente es su DNI: la conoce el
    administrador que la asignó y cualquiera que tenga el dato. Una clave
    que conocen dos personas no identifica a ninguna, y la asistencia se
    firma a nombre de una sola, así que mientras siga puesta el sistema
    no deja pasar de «Mi cuenta».

    Va aquí y no en cada vista porque un olvido en una sola vista abriría
    el sistema entero: basta con conocer su dirección.
    """

    # Lo único que se puede hacer con la clave pendiente: cambiarla o irse.
    # (Los archivos de diseño los sirve WhiteNoise antes de llegar aquí.)
    PERMITIDO = ("cambiar-clave", "login", "logout")

    def __init__(self, get_response):
        self.get_response = get_response
        self.rutas_libres = None

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if (
            usuario is not None
            and usuario.is_authenticated
            and getattr(usuario, "debe_cambiar_clave", False)
            and request.path not in self.libres()
        ):
            return redirect("cambiar-clave")
        return self.get_response(request)

    def libres(self):
        # Se resuelven una vez, no en cada petición; las rutas no cambian
        # mientras el proceso vive.
        if self.rutas_libres is None:
            self.rutas_libres = {reverse(nombre) for nombre in self.PERMITIDO}
        return self.rutas_libres
