@echo off
title Monitor Sensor de Gas MiCS-5524 (Wi-Fi Inalambrico)
echo ============================================================
echo  Iniciando Monitor de Gas MiCS-5524 y ESP32-S3 Inalambrico
echo  Tesis UTEC 2026
echo ============================================================
cd /d "%~dp0pruebas\sensor_gas"
python visor_gas_python.py --wifi 192.168.4.1
pause
