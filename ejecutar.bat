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
echo    ASISTENCIA UNAP
echo.
echo    Abre el navegador en:   http://localhost:8000
echo.
echo    Para apagar: pulsa Ctrl+C o cierra esta ventana.
echo    Recuerda tener MySQL encendido en XAMPP.
echo ===========================================================
echo.

app\Scripts\python.exe manage.py runserver 8000

echo.
echo El servidor se detuvo.
pause
