@echo off
title Visor ESP32-S3 Camara UVC - OpenCV
echo ============================================================
echo  Iniciando Visor de Camara UVC en Tiempo Real (OpenCV)
echo  Tesis UTEC 2026 - Conexion COM12 a 1,500,000 baudios
echo ============================================================
cd /d "%~dp0"
python visor_camara_serial.py COM12 1500000
pause
