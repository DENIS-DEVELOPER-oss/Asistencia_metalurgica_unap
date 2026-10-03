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
echo    ASISTENCIA UNAP  -  acceso desde el celular
echo ===========================================================
echo.
echo Direcciones IP de esta computadora:
echo.
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /c:"IPv4"') do echo    http://%%A:8000
echo.
echo Entra desde el celular a una de esas direcciones
echo ^(el celular debe estar en la MISMA red Wi-Fi^).
echo.
echo IMPORTANTE: esa IP debe estar escrita en el archivo .env,
echo en la linea ALLOWED_HOSTS. Si no, el navegador dara error.
echo.
echo Para apagar: pulsa Ctrl+C o cierra esta ventana.
echo ===========================================================
echo.

app\Scripts\python.exe manage.py runserver 0.0.0.0:8000

echo.
echo El servidor se detuvo.
pause
