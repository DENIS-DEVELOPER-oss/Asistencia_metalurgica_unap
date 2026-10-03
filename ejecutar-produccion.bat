@echo off
cd /d "%~dp0"

if not exist "app\Scripts\python.exe" (
    echo.
    echo   No esta instalado todavia.
    echo   Ejecuta primero:  instalar.bat
    echo.
    pause
    exit /b 1
)

echo.
echo ===========================================================
echo    ASISTENCIA UNAP  -  modo de uso real
echo ===========================================================
echo.
echo Preparando los archivos de diseno...
app\Scripts\python.exe manage.py collectstatic --noinput >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR al preparar los archivos. Detalle:
    app\Scripts\python.exe manage.py collectstatic --noinput
    pause
    exit /b 1
)
echo       Listos.
echo.

app\Scripts\python.exe servidor.py

echo.
echo El servidor se detuvo.
pause
