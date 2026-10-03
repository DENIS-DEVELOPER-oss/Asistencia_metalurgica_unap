# Asistencia UNAP — cómo instalarlo en esta computadora

Sistema de control de asistencia para cursos de la **Universidad Nacional del Altiplano
Puno**. Llama lista desde el celular o la PC e imprime los reportes en **Excel, Word y
PDF**.

Este paquete trae **el código completo y la base de datos con sus datos**. En una
computadora nueva se instala en unos 5 minutos.

---

## Antes de empezar: dos programas

| Programa | Dónde se consigue | Nota al instalar |
|---|---|---|
| **Python 3.10 o superior** | <https://www.python.org/downloads/> | ⚠️ Marca la casilla **«Add Python to PATH»** en la primera pantalla |
| **XAMPP** (trae MySQL/MariaDB) | <https://www.apachefriends.org/> | Solo se necesita el módulo **MySQL** |

> ⚠️ **Importante sobre la base de datos:** este sistema necesita **MySQL 8** o
> **MariaDB 10.5 o superior**. Las versiones de XAMPP anteriores a 2024 traen MariaDB
> 10.4, con la que Django **no** se conecta. Para saber qué versión tienes, abre el Panel
> de Control de XAMPP, inicia MySQL y pulsa *Shell*, luego escribe:
> ```
> mysql -u root -e "SELECT VERSION();"
> ```
> Si sale 10.4 o menos, descarga la última versión de XAMPP o instala MySQL 8 aparte.

---

## Instalación en 3 pasos

### 1. Copia la carpeta

Descomprime el ZIP donde quieras, por ejemplo en `C:\asistencia-unap`.

> Evita rutas con OneDrive o con tildes en el nombre; dan problemas.

### 2. Enciende MySQL

Abre el **Panel de Control de XAMPP** y pulsa **Start** en la fila de **MySQL**.
Debe quedar en verde.

### 3. Doble clic en `instalar.bat`

El script hace todo solo:
- crea el entorno virtual de Python,
- instala las librerías necesarias,
- crea el archivo de configuración,
- e **importa la base de datos con todos los datos**.

Cuando termine sin errores, ya está instalado.

---

## Usarlo todos los días

**Doble clic en `ejecutar-produccion.bat`** y abre <http://localhost:8000>
en el navegador. Ese es el modo con el que se usa de verdad: aguanta que
varios docentes entren a la vez y no enseña datos del sistema si algo
falla.

`ejecutar.bat` sigue ahí, pero es el modo de pruebas: atiende de uno en
uno y muestra los detalles de cualquier error en pantalla.

Para apagarlo, cierra la ventana negra o pulsa `Ctrl + C` en ella.

> Recuerda tener **MySQL encendido en XAMPP** antes de abrir la aplicación.

### Usuarios

| Usuario | Contraseña | Qué puede hacer |
|---|---|---|
| `01340274` | `01340274` | **Docente**: llamar asistencia en sus cursos e imprimir sus reportes |
| `axiomresearch322@gmail.com` | `76505415` | **Administrador**: crear cursos y periodos, matricular alumnos, gestionar docentes y consultar los reportes de todos |

**Cámbialas apenas entres**, en *Mi cuenta* (en la barra de la izquierda).
Desde ahí también puedes cambiar el usuario con el que entras.

> ⚠️ La contraseña de la docente es su DNI. Es cómodo para repartirla el
> primer día, pero cualquiera que conozca su DNI puede entrar en su nombre
> y firmar asistencia por ella. Conviene que la cambie apenas entre.

> **Llamar asistencia solo lo hace el docente del curso.** La clase queda
> firmada a su nombre, así que ni el administrador puede tomarla por él. El
> administrador sí ve el historial y los reportes de todos los grupos, y si
> hace falta cambiar quién dicta un curso lo hace en *Administración →
> Grupos y docente asignado*.

---

> Las dos contraseñas de arriba están escritas en este archivo, así que las
> conoce cualquiera que tenga el paquete. Por eso el sistema no te deja usarlas
> más de una vez: al entrar te pide elegir una propia antes de dejarte hacer
> nada más.


## Matricular a los estudiantes de un curso

Entra como **administrador**, abre el curso → *Estudiantes matriculados* →
**Agregar estudiantes**.

Hay dos pestañas:

- **Registrar estudiantes nuevos** — para alumnos que todavía no están en el
  sistema. Pega la lista, un alumno por línea:

  ```
  CÓDIGO;APELLIDO PATERNO;APELLIDO MATERNO;NOMBRES
  266197;QUISPE;MAMANI;JUAN CARLOS
  266483;CONDORI;APAZA;MARIA LUZ;maria@unap.edu.pe
  ```

  El correo del final es opcional. También puedes copiar las columnas
  directamente desde Excel y pegarlas: llegan separadas por tabulador y el
  sistema las entiende igual. Quedan registrados **y matriculados** en el curso
  de un solo paso.

- **Ya están en la base** — si el alumno ya existe, basta con pegar su código.

Si una línea está mal escrita, el sistema te dice el número de línea y registra
igualmente las demás.

---

## Cambiar usuarios y contraseñas

- **La tuya**: *Mi cuenta*, en la barra de la izquierda. Ahí cambias tanto
  la contraseña como el usuario con el que entras.
- **La de un docente**: entra como administrador a *Administración* →
  pestaña **Docentes**. El botón «Editar» de cada fila cambia sus datos y
  su usuario; el campo de la derecha le pone una contraseña nueva.


## Seguridad

El sistema guarda el registro oficial de asistencia del curso, así que viene con
varias protecciones puestas de fábrica. No hay que configurar nada.

**Nadie puede probar contraseñas a la fuerza.** Tras **5 intentos fallidos** con
la misma cuenta (o 20 desde el mismo equipo), el acceso queda en espera **15
minutos**. Se levanta solo; no hay que desbloquear nada a mano. Esto importa
porque la contraseña inicial de un docente es su DNI, y ocho dígitos se prueban
rápido si nadie lo impide.

**Queda constancia de lo que se hace.** Administración → *Registro de seguridad*
(o el escudo de la barra izquierda) muestra quién entró, quién lo intentó sin
lograrlo y qué se cambió: cursos creados o eliminados, docentes dados de alta o
de baja, contraseñas asignadas, estudiantes matriculados. Se guardan 180 días.

**La sesión caduca sola.** A las 3 horas sin usar el sistema hay que volver a
entrar; el contador se reinicia con cada pantalla que se abre, así que una clase
entera no se corta. Y después de cerrar sesión, el botón «atrás» del navegador ya
no devuelve la lista de alumnos: importa en la PC compartida del aula.

**Una contraseña que puso otro sirve para entrar una vez.** Cuando el
administrador crea un docente o le asigna una contraseña, esa clave la conocen
dos personas. La primera vez que el docente entre, el sistema lo lleva a *Mi
cuenta* y no lo deja pasar de ahí hasta que elija una propia. Importa porque la
asistencia queda firmada a su nombre: mientras la clave la sepa alguien más, esa
firma no prueba nada. En *Administración → Docentes*, la columna **Contraseña**
dice en qué estado está cada una: *Propia*, *Sin cambiar* o *Sin definir*.

**La aplicación no entra a MySQL como root.** Tiene su propia cuenta
(`asistencia_app`) con una contraseña larga guardada en el `.env`, y con permiso
para leer y escribir filas de `asistencia_unap` y nada más: no puede borrar
tablas ni cambiar su estructura. Esto tapa el agujero más silencioso del
sistema: todas sus reglas —que no se pueda tocar una clase cerrada, que solo el
docente titular firme— se aplican *dentro* de la aplicación, y quien se conecta
a la base por debajo se las salta todas. `instalar.bat` crea esa cuenta solo;
para renovar su contraseña, `manage.py crear_usuario_mysql`.

**Copia de seguridad con un comando.**

```
app\Scripts\python.exe manage.py respaldar
```

Guarda un archivo con la fecha en la carpeta `respaldos/` y conserva los 10
últimos. Llévate una copia a un USB o a la nube: un respaldo que vive en la
misma PC no sirve si es la PC lo que se pierde. Para restaurar, las
instrucciones están en la cabecera del propio comando y en `usuarios.txt`.

**Revisión de un vistazo.** Antes de abrir el sistema al ciclo, en la ventana
negra:

```
app\Scripts\python.exe manage.py revisar_seguridad
```

Repasa la configuración, la cuenta de MySQL, las cuentas de las personas, los
respaldos y el registro de los últimos días, y dice qué conviene corregir.

### Lo que queda por hacer, y no depende del código

1. **HTTPS.** En la red de la universidad las páginas viajan por HTTP, así que
   la contraseña va sin cifrar por la red local. El día que el área de sistemas
   ponga un certificado delante, basta con escribir `USAR_HTTPS=True` en el
   `.env`.
2. **Cerrar el puerto de MySQL.** Hoy MySQL acepta conexiones de toda la red
   (puerto 3306) y nada del sistema lo necesita: la aplicación y la base están
   en la misma PC, y los celulares entran por el 8000. En el Panel de XAMPP →
   fila *MySQL* → *Config* → `my.ini`, en la sección `[mysqld]`, añade
   `bind-address=127.0.0.1`, guarda y reinicia MySQL. Si algo dejara de
   funcionar, borra la línea y reinicia otra vez.
3. **Contraseña para root.** root entra a MySQL sin contraseña; hoy solo se
   puede desde esta misma PC, así que el riesgo es menor, y ponérsela obliga a
   actualizar la configuración de phpMyAdmin.


## Crear un periodo académico

Los cursos se abren dentro de un periodo (`2026-I`, `2026-II`…). Para agregar
uno nuevo: menú de tu foto → *Administración* → **Periodos académicos** →
*Nuevo periodo*.

---

## Usarlo desde el celular en el aula

1. Conecta el celular a la **misma red Wi-Fi** que la computadora.
2. Averigua la IP de la computadora: abre la ventana negra y escribe `ipconfig`.
   Busca *Dirección IPv4*, algo como `192.168.1.40`.
3. Abre el archivo `.env` con el Bloc de notas y agrega esa IP:
   ```
   ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.40
   ```
4. Arranca con `ejecutar-en-red.bat` en vez de `ejecutar.bat`.
5. En el celular entra a `http://192.168.1.40:8000`.

---

## Qué trae el paquete

```
asistencia-unap/
├── LEEME-PRIMERO.md        este archivo
├── README.md               documentación técnica completa
├── instalar.bat            instalación automática
├── ejecutar.bat            arranca la aplicación
├── ejecutar-en-red.bat     arranca permitiendo el acceso desde el celular
├── manage.py               punto de entrada de Django
├── requirements.txt        librerías de Python
├── base_de_datos/
│   ├── asistencia_unap_instalar.sql    ← la base completa (se importa sola)
│   ├── asistencia_unap_completo.sql    copia de respaldo del volcado anterior
│   ├── asistencia_unap_original.sql    script original de creación
│   └── REPORTE OFICIAL (referencia).pdf
├── config/ cuentas/ academico/ asistencia/ reportes/    código
├── templates/              pantallas
├── static/                 diseño
└── respaldos/              copias de la base (las crea manage.py respaldar)
```

---

## Si algo sale mal

**`instalar.bat` dice que no encuentra Python**
No marcaste «Add Python to PATH» al instalarlo. Reinstala Python y marca esa casilla.

**`instalar.bat` dice que no encuentra MySQL**
Importa la base a mano: abre <http://localhost/phpmyadmin>, pestaña **Importar**, elige
`base_de_datos\asistencia_unap_instalar.sql` y pulsa *Continuar*. Después vuelve a
ejecutar `instalar.bat`.

> El archivo se puede importar las veces que haga falta: crea lo que falta y no
> borra nada, así que **no se pierde la asistencia ya registrada**.

**Al abrir la app: `Can't connect to MySQL server`**
MySQL está apagado. Enciéndelo desde el Panel de Control de XAMPP.

**Al abrir la app: `MariaDB 10.5 or later is required`**
Tu XAMPP trae una versión vieja. Mira la advertencia del inicio de este archivo.

**`Usuario o contraseña incorrectos` con los usuarios de la tabla**
La base no se importó bien. Vuelve a importarla con phpMyAdmin.

**`Demasiados intentos fallidos: el acceso queda en espera N minutos`**
Es la protección contra quien prueba contraseñas: salta a los 5 fallos seguidos.
No hay nada que desbloquear, se levanta solo en esos minutos. Si la contraseña se
perdió de verdad, el administrador le asigna otra en *Administración → Docentes*.

**Entro y siempre me deja en «Mi cuenta», no puedo ir a ningún otro sitio**
No está roto: la contraseña con la que entraste la puso el administrador, y el
sistema pide que elijas una propia antes de seguir. Llena el formulario
*Contraseña* de la derecha y al guardarlo te lleva a tus cursos.

**Después de crear la cuenta de MySQL, la app dice `Access denied for user`**
El `.env` y MySQL no dicen lo mismo. Vuelve a ejecutar
`app\Scripts\python.exe manage.py crear_usuario_mysql`, que rehace la cuenta y
reescribe el `.env` de una vez. Si root tiene contraseña, añade
`--admin-clave "LA DE ROOT"`.

**Quiero volver a que la app entre a MySQL como antes**
Abre el `.env` con el Bloc de notas, pon `DB_USER=root` y deja `DB_PASSWORD=`
vacío. Funciona, pero queda menos protegido; `manage.py revisar_seguridad` te lo
recordará.

**Se ve todo sin colores ni escudo**
Falta preparar los archivos de diseño. Ejecuta en la ventana negra:
`app\Scripts\python.exe manage.py collectstatic --noinput`.
`ejecutar-produccion.bat` ya lo hace solo cada vez.

**Al arrancar avisa `SECRET_KEY sigue siendo la clave de ejemplo`**
Falta el archivo `.env`, o todavía tiene la clave de ejemplo. Vuelve a ejecutar
`instalar.bat` (lo crea con una clave nueva), o copia `.env.example` como `.env` y
pon tu propia clave en la línea `SECRET_KEY=`.

**El puerto 8000 está ocupado**
Arranca en otro puerto: abre la ventana negra en esta carpeta y escribe
`app\Scripts\python.exe manage.py runserver 8080`, luego entra a
<http://localhost:8080>.
