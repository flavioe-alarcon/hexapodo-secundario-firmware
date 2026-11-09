@echo off
title Monitor Sensor de Gas MiCS-5524 (Serial COM - OpenCV)
echo ============================================================
echo  Iniciando Monitor de Gas MiCS-5524 y ESP32-S3 (OpenCV)
echo  Modo: Serial USB (COM12 / Auto-detect a 115,200 baudios)
echo  Tesis UTEC 2026
echo ============================================================
cd /d "%~dp0"
python visor_gas_python.py COM12 115200
pause
