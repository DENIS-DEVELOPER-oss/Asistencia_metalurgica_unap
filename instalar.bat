@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ===========================================================
echo    ASISTENCIA UNAP  -  Instalacion
echo    Universidad Nacional del Altiplano Puno
echo ===========================================================
echo.

REM ----------------------------------------------------------------
REM  1. Python
REM ----------------------------------------------------------------
echo [1/5] Buscando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: no se encontro Python.
    echo.
    echo   Instalalo desde https://www.python.org/downloads/
    echo   y MARCA la casilla "Add Python to PATH" en la primera pantalla.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set "PYVER=%%V"
echo       Python !PYVER! encontrado.
echo.

REM ----------------------------------------------------------------
REM  2. Entorno virtual
REM ----------------------------------------------------------------
echo [2/5] Preparando el entorno virtual...
if exist "app\Scripts\python.exe" (
    echo       Ya existia, se reutiliza.
) else (
    python -m venv app
    if errorlevel 1 (
        echo   ERROR: no se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo       Creado.
)
echo.

REM ----------------------------------------------------------------
REM  3. Librerias
REM ----------------------------------------------------------------
echo [3/5] Instalando librerias ^(puede tardar unos minutos^)...
app\Scripts\python.exe -m pip install --upgrade pip --quiet
app\Scripts\python.exe -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo   ERROR: fallo la instalacion de librerias.
    echo   Revisa que tengas conexion a internet y vuelve a intentar.
    echo.
    pause
    exit /b 1
)
echo       Listas.
echo.

REM ----------------------------------------------------------------
REM  4. Configuracion
REM ----------------------------------------------------------------
echo [4/5] Configuracion...
if exist ".env" (
    echo       El archivo .env ya existe, no se toca.
) else (
    copy ".env.example" ".env" >nul
    app\Scripts\python.exe -c "import secrets,pathlib; p=pathlib.Path('.env'); p.write_text(p.read_text(encoding='utf-8').replace('django-inseguro-cambia-esta-clave-en-produccion', secrets.token_urlsafe(50)), encoding='utf-8')"
    echo       Archivo .env creado con una clave secreta nueva.
)
echo.

REM ----------------------------------------------------------------
REM  5. Base de datos
REM ----------------------------------------------------------------
echo [5/5] Importando la base de datos...

REM XAMPP no siempre esta en C:. Se recorren todas las unidades, porque
REM instalarlo en D: era motivo suficiente para que la base nunca se
REM importara y la aplicacion arrancara sin datos.
set "MYSQL="
for %%D in (C D E F G H) do call :buscar_mysql %%D
if not defined MYSQL for /f "delims=" %%I in ('where mysql 2^>nul') do set "MYSQL=%%I"
goto :mysql_encontrado

:buscar_mysql
if defined MYSQL goto :eof
if not exist "%~1:\" goto :eof
if exist "%~1:\xampp\mysql\bin\mysql.exe" set "MYSQL=%~1:\xampp\mysql\bin\mysql.exe"
if defined MYSQL goto :eof
REM Rutas con numero de version: se resuelven con comodin.
for /d %%P in ("%~1:\Program Files\MySQL\MySQL Server *") do if exist "%%P\bin\mysql.exe" set "MYSQL=%%P\bin\mysql.exe"
if defined MYSQL goto :eof
for /d %%P in ("%~1:\Program Files\MariaDB *") do if exist "%%P\bin\mysql.exe" set "MYSQL=%%P\bin\mysql.exe"
if defined MYSQL goto :eof
for /d %%P in ("%~1:\laragon\bin\mysql\*") do if exist "%%P\bin\mysql.exe" set "MYSQL=%%P\bin\mysql.exe"
if defined MYSQL goto :eof
for /d %%P in ("%~1:\wamp64\bin\mysql\*") do if exist "%%P\bin\mysql.exe" set "MYSQL=%%P\bin\mysql.exe"
goto :eof

:mysql_encontrado

if not defined MYSQL (
    echo.
    echo   AVISO: no se encontro mysql.exe, asi que no pude importar la base.
    echo.
    echo   Hazlo a mano, es facil:
    echo     1^) Enciende MySQL en el Panel de Control de XAMPP.
    echo     2^) Abre http://localhost/phpmyadmin
    echo     3^) Pestana "Importar" -^> elegir archivo:
    echo        %~dp0base_de_datos\asistencia_unap_instalar.sql
    echo     4^) Pulsa "Continuar".
    echo.
    pause
    goto :fin
)

echo       Usando: !MYSQL!
"!MYSQL!" -u root -e "SELECT 1;" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: MySQL esta apagado o pide contrasena.
    echo   Enciende MySQL en el Panel de Control de XAMPP y vuelve a ejecutar
    echo   este instalador.
    echo.
    pause
    exit /b 1
)

"!MYSQL!" -u root --default-character-set=utf8mb4 < "base_de_datos\asistencia_unap_instalar.sql"
if errorlevel 1 (
    echo.
    echo   ERROR: no se pudo importar la base de datos.
    echo   Intentalo desde phpMyAdmin con el archivo:
    echo     base_de_datos\asistencia_unap_instalar.sql
    echo.
    pause
    exit /b 1
)
echo       Base de datos importada.
echo.

REM ----------------------------------------------------------------
REM  Cuenta de MySQL propia para la aplicacion
REM ----------------------------------------------------------------
REM  Sin esto la aplicacion entra a la base como root sin contrasena, y
REM  cualquier programa de esta PC podria cambiar la asistencia ya
REM  registrada saltandose las reglas del sistema. Si falla no se corta la
REM  instalacion: el sistema funciona igual, solo queda menos protegido.
echo Creando la cuenta de MySQL de la aplicacion...
app\Scripts\python.exe manage.py crear_usuario_mysql
if errorlevel 1 (
    echo.
    echo   AVISO: no se pudo crear la cuenta propia y la aplicacion seguira
    echo   entrando como root. Si root tiene contrasena, ejecuta despues:
    echo     app\Scripts\python.exe manage.py crear_usuario_mysql --admin-clave "LA DE ROOT"
    echo.
)
echo.

REM ----------------------------------------------------------------
REM  Comprobacion final
REM ----------------------------------------------------------------
echo Comprobando que todo quede en orden...
app\Scripts\python.exe manage.py check
if errorlevel 1 (
    echo.
    echo   La comprobacion encontro problemas. Revisa los mensajes de arriba.
    echo   Lo mas comun: MySQL apagado, o una version de MariaDB anterior a 10.5.
    echo.
    pause
    exit /b 1
)

:fin
echo.
echo ===========================================================
echo    INSTALACION TERMINADA
echo.
echo    Para usar el sistema: doble clic en  ejecutar.bat
echo    Luego abre:           http://localhost:8000
echo.
echo    Usuario docente: ralvarez / Asistencia2026
echo    Administrador:   admin    / AdminUnap2026
echo.
echo    Esas dos contrasenas estan escritas en el LEEME, asi que las
echo    conoce cualquiera que tenga este paquete: al entrar, el sistema
echo    te pedira elegir una propia antes de dejarte hacer nada mas.
echo.
echo    Revision de seguridad, cuando quieras:
echo      app\Scripts\python.exe manage.py revisar_seguridad
echo ===========================================================
echo.
pause
