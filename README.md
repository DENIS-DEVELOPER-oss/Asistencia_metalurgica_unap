# Sistema de Control de Asistencia — UNAP

Aplicación web para **llamar asistencia** en cursos de la Universidad Nacional del
Altiplano Puno e **imprimir los reportes en Excel, Word y PDF**.

Un solo proyecto **Django**: las pantallas se renderizan con plantillas, no hay frontend
aparte, ni Node, ni paso de compilación. Se levanta con un comando.

> La base de datos `asistencia_unap` es la **fuente de verdad**. Todos los modelos son
> `managed = False` y **toda la lógica de asistencia pasa por los procedimientos
> almacenados** (`sp_iniciar_sesion`, `sp_marcar_asistencia`, `sp_cerrar_sesion`).

---

## 1. Arrancar la aplicación

Con MySQL/MariaDB encendido (en XAMPP: botón **Start** junto a MySQL):

```powershell
cd d:\AP_ING_RUBY_ASISTENCIA
.\app\Scripts\python.exe manage.py runserver 8000
```

Abre **<http://localhost:8000>**. `Ctrl+C` para detener.

| Usuario | Contraseña | Rol |
|---|---|---|
| `ralvarez` | `Asistencia2026` | Docente (ALVAREZ ARTEAGA RUBY JUNIORS) |
| `admin` | `AdminUnap2026` | Administrador |

---

## 2. Instalación desde cero

Solo hace falta si mueves el proyecto a otra computadora.

### Requisitos

| Componente | Versión | Nota |
|---|---|---|
| Python | 3.10 o superior | |
| MySQL 8 **o** MariaDB 10.5+ | | Django 5.2 rechaza MariaDB 10.4 o anterior |

### Paso 1 — Importar la base de datos

```powershell
Get-Content asistencia_unap.sql -Raw -Encoding UTF8 | C:\xampp\mysql\bin\mysql.exe -u root --default-character-set=utf8mb4
```

Crea `asistencia_unap` con 11 tablas, 3 vistas, 3 procedimientos, 2 triggers y los datos
del reporte oficial MET201 – Grupo B (28 estudiantes).

> ⚠️ El script empieza con `DROP DATABASE IF EXISTS asistencia_unap`. Si ya tienes datos
> reales, respáldalos antes de volver a ejecutarlo.

### Paso 2 — Entorno e instalación

```powershell
.\app\Scripts\Activate.ps1          # o usa .\app\Scripts\python.exe directamente
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` con los datos de tu servidor:

```ini
SECRET_KEY=pon-aqui-una-clave-larga-y-aleatoria
DEBUG=True
DB_NAME=asistencia_unap
DB_USER=root
DB_PASSWORD=            # XAMPP viene sin contraseña de root
DB_HOST=127.0.0.1
DB_PORT=3306
UMBRAL_INHABILITACION=30
```

> **No ejecutes `python manage.py migrate`.** El esquema lo define `asistencia_unap.sql`.
> Las sesiones de login se guardan firmadas en la cookie del navegador, así que el
> sistema no necesita crear ni una sola tabla extra.

### Paso 3 — Crear las contraseñas

El script SQL deja las cuentas con `password_hash = 'PENDIENTE_DEFINIR'`, que no es un
hash válido: sin este paso nadie puede entrar.

```powershell
python manage.py set_password ralvarez --password "Asistencia2026"
python manage.py crear_admin admin --password "AdminUnap2026"
```

Sin `--password` las pide por teclado. Usa `--sin-validar` para saltarte las reglas de
robustez.

### Paso 4 — Levantar

```powershell
python manage.py runserver 8000
```

> **Desde el celular:** conecta el celular a la misma red Wi-Fi, agrega la IP de tu PC a
> `ALLOWED_HOSTS` en `.env` y arranca con `python manage.py runserver 0.0.0.0:8000`.
> Luego abre `http://<IP-de-tu-PC>:8000` en el celular.

---

## 3. Cómo se usa

1. **Iniciar sesión** con el usuario del docente.
2. **Mis cursos** — un panel por grupo con alumnos, % de asistencia y última clase.
   Un docente puede tener **todos los cursos que necesite**; el **selector de la barra
   superior** salta de uno a otro sin volver al inicio y mantiene la pantalla en la que
   estás (Asistencia, Historial o Reporte).

   **Gestionar cursos es tarea del ADMIN** (el docente no ve estos botones y, si entra
   por URL directa, recibe un 403):
   - **Nuevo curso** — código, nombre, sección, créditos, semestre, escuela, periodo y
     docente a cargo. Al crearlo lleva a la pantalla de matrícula.
   - **Editar** — en cada panel: nombre del curso, código, créditos, semestre y sección.
   - **Eliminar** — borra el curso y sus matrículas. Si ya tiene clases registradas
     **no se permite**: esa asistencia es el registro oficial y no debe perderse por un
     clic.
   - **Estudiantes** — matricula por código (uno por línea) o retira a alguien. No se
     puede retirar a un alumno que ya tiene asistencia registrada. El docente sí puede
     **ver** la lista.
3. **Llamar asistencia** — eliges fecha, hora y tema, y pulsas *Iniciar clase*.
   `sp_iniciar_sesion` crea la lista con los 28 matriculados, todos como **Falta**.
   - Marcas a cada alumno con los botones **P / T / F / J**.
   - *Marcar todos presentes* cambia los 28 de un golpe (y luego corriges las excepciones).
   - El buscador filtra por nombre o código mientras escribes.
   - Los contadores de arriba se actualizan en vivo.
   - Puedes agregar una **observación** por alumno con el botón del globo.
   - Pulsa **Guardar asistencia**. Solo se envían a la base los alumnos que cambiaron.
4. **Guardar y cerrar clase** — pide confirmación y llama a `sp_cerrar_sesion`. A partir
   de ahí el trigger `trg_asistencia_sesion_cerrada` bloquea cualquier cambio y la
   pantalla queda en solo lectura.
5. **Historial** — todas las clases del grupo con su resumen y el PDF de cada una.
6. **Reporte** — tabla por alumno con barra de % y semáforo
   (≥85 % verde · 70–84 % ámbar · <70 % rojo), resaltando a quienes superan el **30 %
   de faltas** (riesgo de inhabilitación).
7. **Administración** (solo ADMIN) — registrar docentes, asignarles contraseña y
   asignar el docente de cada grupo.

### Qué puede hacer cada rol

| Acción | Docente | Admin |
|---|:--:|:--:|
| Ver sus cursos, llamar asistencia, cerrar clase | ✅ | ✅ |
| Ver el historial, el reporte y la lista de matriculados | ✅ | ✅ |
| Descargar Excel / Word / PDF | ✅ | ✅ |
| Crear, editar y eliminar cursos | — | ✅ |
| Matricular y retirar estudiantes | — | ✅ |
| Registrar docentes y asignar contraseñas | — | ✅ |

Un docente solo ve los grupos donde `grupo.id_docente` es el suyo; el admin ve todo.

La barra superior tiene el **buscador** de cursos y el botón de **modo claro / oscuro**.

---

## 4. Los reportes

**Por curso** — pantalla *Reporte*, tres botones:

| Formato | Archivo | Contenido |
|---|---|---|
| **Excel** | `MET201_GrupoB_2026-II_asistencia.xlsx` | Hoja *Resumen* (totales con formato condicional verde/ámbar/rojo, filtros y panel inmovilizado) y hoja *Detalle* (matriz alumno × fecha) |
| **Word** | `MET201_GrupoB_2026-II_asistencia.docx` | Reporte completo editable, con la matriz coloreada y espacio de firma |
| **PDF** | `MET201_GrupoB_2026-II_asistencia.pdf` | Formato oficial: encabezado institucional, matriz, totales, «Pág. X/Y» y firma |

**Por clase** — pantalla *Historial* (botones XLS / DOC / PDF en cada fila) o la propia
pantalla de asistencia: la lista de esa sesión con su tema, resumen y observaciones
(`MET201_GrupoB_2026-II_2026-09-19_lista.xlsx`).

**De todos los cursos** — botón *Excel de todos mis cursos* en «Mis cursos»:
`Asistencia_todos_2026-09-19_consolidado.xlsx`, con una hoja **General** (una fila por
curso: alumnos, clases, % promedio y alumnos en riesgo) más una hoja por curso con su
matriz.

Todos llevan **fecha y hora de emisión**. Todos usan los mismos datos
(`reportes/datos.py`), así que siempre coinciden entre sí. Si hay muchas fechas, el PDF
y el Word cambian solos a orientación horizontal.

---

## 5. Estructura

```
AP_ING_RUBY_ASISTENCIA/
├── manage.py                  Punto de entrada de Django
├── asistencia_unap.sql        Script de la base de datos (no modificar)
├── requirements.txt / .env
├── app/                       Entorno virtual de Python
├── config/                    Ajustes, URLs, formatos es-PE, páginas de error
├── cuentas/                   Usuario personalizado, docentes, login, panel admin
│   └── management/commands/   set_password · crear_admin
├── academico/                 Facultad, escuela, curso, grupo, matrícula, permisos
│   └── gestion.py             Alta, edición y baja de cursos y matrículas
├── asistencia/                Sesiones de clase y marcado (llama a los procedimientos)
│   ├── services.py            callproc de los 3 SP
│   └── errores.py             Traduce los SIGNAL 45000 de la base
├── reportes/                  datos.py · excel.py · word.py · pdf.py
├── templates/                 base.html + una plantilla por pantalla
├── static/css/estilos.css     Todo el diseño (sin frameworks)
└── _backup_mysql/             Respaldos previos a la actualización de MariaDB
```

---

## 6. Decisiones que conviene conocer

- **Nada de migraciones.** Modelos con `managed = False` y `db_table` explícito.
  `MIGRATION_MODULES` desactiva las migraciones de `auth`, `contenttypes` y `sessions`
  para que `migrate` no cree tablas auxiliares.
- **Sesiones en cookie firmada** (`SESSION_ENGINE = signed_cookies`): el login funciona
  sin la tabla `django_session`.
- **Usuario personalizado sin `PermissionsMixin`.** `cuentas.Usuario` extiende
  `AbstractBaseUser` sobre la tabla `usuario`: `password → password_hash`,
  `last_login → ultimo_acceso`, `is_active → activo`. La autorización se basa en `rol`.
- **Los procedimientos almacenados mandan.** `asistencia/services.py` los invoca con
  `connection.cursor().callproc(...)`; el `OUT` de `sp_iniciar_sesion` se lee con
  `SELECT @_sp_iniciar_sesion_5`. Los `SIGNAL SQLSTATE '45000'` de triggers y
  procedimientos se muestran al docente como un aviso en rojo con el texto que emite la
  propia base.
- **`USE_TZ = False`** con `TIME_ZONE = America/Lima`: `fecha` y `hora_inicio` son la
  hora local del aula.
- **Separador decimal punto** (`config/formats/`): Django localiza `es` con coma, y una
  coma dentro de `style="width:..%"` rompería las barras del reporte.
- **Accesibilidad:** cada estado se distingue por **color + letra + nombre**, nunca solo
  por color.
- Solo dependencias de Python; el diseño es un único CSS propio, así que la app funciona
  sin internet (salvo la tipografía Inter, que tiene respaldo del sistema).

---

## 7. Cambios hechos en este equipo

1. **MariaDB de XAMPP actualizado de 10.4.32 a 10.11.19 LTS**, porque Django 5.2 exige
   MariaDB ≥ 10.5.
   - La instalación anterior quedó en `C:\xampp\mysql_mariadb104_backup` (no se borró).
   - Los respaldos SQL previos están en `_backup_mysql\`.
   - Configuración nueva en `C:\xampp\mysql\bin\my.ini` (mismo puerto 3306 y utf8mb4,
     para que el Panel de Control de XAMPP funcione igual).
   - Para revertir: detén MySQL, borra `C:\xampp\mysql`, renombra
     `mysql_mariadb104_backup` a `mysql` y arranca de nuevo.
2. **Node.js 24.19.0** se instaló para una versión anterior del proyecto que usaba Vue.
   Ya **no hace falta** y puedes desinstalarlo sin afectar la aplicación.

---

## 8. Problemas frecuentes

**`NotSupportedError: MariaDB 10.5 or later is required`**
Tu servidor es anterior a 10.5. Actualiza MariaDB o instala MySQL 8.

**`Usuario o contraseña incorrectos`, aunque el usuario existe**
Falta el Paso 3: la contraseña sigue en `PENDIENTE_DEFINIR`. Ejecuta
`python manage.py set_password <usuario>`.

**`Tu cuenta no está vinculada a una ficha de docente`**
El usuario existe en `usuario` pero no tiene fila en `docente`. Créala desde
Administración o enlázala con
`UPDATE docente SET id_usuario = <n> WHERE id_docente = <m>;`

**«Ya existe un registro con esos datos» al iniciar una clase**
La tabla tiene `UNIQUE (id_grupo, fecha, hora_inicio)`: ya abriste una clase de ese
grupo a esa misma hora. Continúala desde *Historial* o cambia la hora de inicio.

**No puedo modificar la asistencia de una clase**
Está cerrada. Es a propósito: el trigger de la base lo impide y la pantalla queda en
solo lectura. Abre una clase nueva si necesitas registrar otra sesión.


## Pruebas

```bash
python manage.py test
```

Las pruebas de `pruebas/` son todas `SimpleTestCase`: **no abren MySQL**, así
que corren con la base apagada y en cualquier máquina. Cubren

- el parseo de la lista de estudiantes que se pega al matricular,
- los validadores de curso, periodo y estado de asistencia,
- la traducción de los errores de MySQL (incluidos los `SIGNAL` de los
  triggers) a mensajes en español,
- el semáforo de asistencia,
- la validación del parámetro `next` del login,
- y la generación de los seis archivos de reporte (Excel, Word y PDF, de grupo
  y de sesión), comprobando que salgan bien formados y con los datos dentro.

Lo que **no** cubren todavía es lo que pasa por los procedimientos almacenados
(`sp_iniciar_sesion`, `sp_marcar_asistencia`, `sp_cerrar_sesion`) y los
triggers: para eso hace falta un MySQL de pruebas con el esquema de
`base_de_datos/asistencia_unap_original.sql` cargado.


## La base de datos

`base_de_datos/asistencia_unap_instalar.sql` es el instalador completo:
estructura, triggers, procedimientos, vistas y datos iniciales en un solo
archivo, compatible con **MySQL 8+** y **MariaDB 10.5+**.

```bash
mysql -u root --default-character-set=utf8mb4 < base_de_datos/asistencia_unap_instalar.sql
```

Está escrito para poder ejecutarse **varias veces sin perder datos**: las
tablas usan `CREATE TABLE IF NOT EXISTS`, los triggers y procedimientos se
borran y se recrean, las vistas usan `CREATE OR REPLACE` y los datos iniciales
van con `INSERT IGNORE`. No hay ningún `DROP DATABASE` ni `TRUNCATE`.

Para empezar de cero hay que borrar la base a mano antes:

```sql
DROP DATABASE asistencia_unap;
```

Los otros dos `.sql` de esa carpeta (`_completo`, el volcado de MariaDB, y
`_original`, el script de creación inicial) se conservan solo como respaldo.

Como los modelos son `managed = False`, Django nunca corrige el esquema: si
el `.sql` y los modelos se separan, la aplicación falla en tiempo de
ejecución. Por eso `pruebas/test_base_de_datos.py` compara el script con cada
`db_table` y `db_column` declarado, y comprueba que los hashes de las cuentas
abran con las contraseñas documentadas.


## Pasar a uso real

`manage.py runserver` es el servidor de desarrollo: atiende de uno en uno
y la propia documentación de Django avisa de que no debe usarse en serio.
Para el uso diario:

```powershell
.\ejecutar-produccion.bat
```

Que hace dos cosas: recoge los archivos estáticos y arranca **Waitress**,
un servidor WSGI en Python puro que funciona en Windows sin compilar nada
y atiende varias peticiones a la vez. Los estáticos los sirve
**WhiteNoise** desde el mismo proceso, comprimidos y con un hash en el
nombre, de modo que no hace falta montar un servidor web delante.

### Antes de ponerlo en uso

En el archivo `.env`:

| Variable | Valor | Por qué |
|---|---|---|
| `DEBUG` | `False` | Con `True`, cualquier error muestra en pantalla la configuración y la contraseña de MySQL |
| `SECRET_KEY` | una clave propia | Las sesiones viajan firmadas con ella; con la de ejemplo se pueden falsificar |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,<IP de la PC>` | Sin la IP, el navegador del celular da error |
| `USAR_HTTPS` | `False` | Solo `True` si el sistema queda detrás de HTTPS |

Con `DEBUG=False` el arranque se corta si la `SECRET_KEY` sigue siendo la
de ejemplo, y los errores dejan de salir en pantalla: se guardan en
`asistencia.log`, que rota cada 2 MB.

`python manage.py check --deploy` no devuelve ningún aviso cuando
`USAR_HTTPS=True`. Sobre HTTP quedan cuatro, todos sobre cookies seguras
y redirección a HTTPS: son inevitables en una red local sin certificado,
y activarlos impediría iniciar sesión.

### Copia de seguridad

La asistencia es el registro oficial del curso. Conviene respaldarla al
cerrar cada semana:

```powershell
D:\xampp\mysql\bin\mysqldump.exe -u root asistencia_unap > respaldo_2026-09-25.sql
```
