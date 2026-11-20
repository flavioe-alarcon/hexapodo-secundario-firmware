@echo off
title Graficador de Telemetria de Corriente - Tesis UTEC
cd /d "%~dp0pruebas\sensor_corriente"
python graficar_csv_corriente.py
pause
