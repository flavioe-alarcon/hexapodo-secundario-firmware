@echo off
title Graficador de Telemetria RPi 5 (Gas MQ-9 y Corriente ACS758)
cd /d "%~dp0pruebas\sensor_gas"

echo ===================================================================
echo   GRAFICADOR DE DATOS RASPBERRY PI 5 (GAS MQ-9 + CORRIENTE)
echo   Selecciona la carpeta ultima_medicion o medicion_anterior
echo ===================================================================
echo.
python graficar_telemetria_rpi.py %*

if errorlevel 1 (
    echo.
    echo [-] Error al graficar. Verifica que Python y matplotlib esten instalados.
    pause
)
