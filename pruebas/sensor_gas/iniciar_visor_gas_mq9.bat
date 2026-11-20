@echo off
title Monitor de Gas MQ-9 & Corriente ACS758 - UTEC 2026
cd /d "%~dp0"

echo ===================================================================
echo   INICIANDO MONITOR DE GAS MQ-9 Y CORRIENTE (ARDUINO NANO COM15)
echo ===================================================================
echo.
python visor_gas_mq9.py COM15

if errorlevel 1 (
    echo.
    echo [-] Error al ejecutar el visor. Verifique que el Arduino Nano este conectado en COM15.
    pause
)
