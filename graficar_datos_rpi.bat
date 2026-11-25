@echo off
title Graficador de Archivos CSV (MQ-9, MiCS-5524 y Corriente ACS758)
cd /d "%~dp0pruebas\sensor_gas"

echo ===================================================================
echo   GRAFICADOR UNICO DE TELEMETRIA (.CSV)
echo   Selecciona cualquier archivo .csv (gas.csv, corriente.csv, MiCS)
echo ===================================================================
echo.
python graficar_telemetria_rpi.py %*

if errorlevel 1 (
    echo.
    echo [-] Error al graficar. Verifica que Python y matplotlib esten instalados.
    pause
)
