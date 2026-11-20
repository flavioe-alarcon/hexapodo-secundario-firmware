@echo off
title Visor Sensor de Corriente ACS758LCB - Robot Primario Chipo
cd /d "%~dp0"

echo ===================================================================
echo   INICIANDO MONITOR DE CORRIENTE ACS758LCB-050B (ARDUINO NANO)
echo ===================================================================
echo.
python visor_corriente_python.py COM15

if errorlevel 1 (
    echo.
    echo [-] Error al ejecutar el visor. Verifique que el Arduino Nano este conectado en COM15.
    pause
)
