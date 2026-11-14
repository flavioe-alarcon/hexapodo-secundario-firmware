@echo off
title Graficador de Datos CSV - Sensor de Gas MiCS-5524
echo ============================================================
echo  Graficador y Analizador de Archivos CSV de Gas
echo  Tesis UTEC 2026
echo  Selecciona un archivo .csv en la ventana que aparecera...
echo ============================================================
cd /d "%~dp0pruebas\sensor_gas"
python graficar_csv_gas.py
pause
