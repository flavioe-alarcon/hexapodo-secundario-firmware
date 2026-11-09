@echo off
title Monitor Sensor de Gas MiCS-5524 (Wi-Fi SoftAP - OpenCV)
echo ============================================================
echo  Iniciando Monitor de Gas MiCS-5524 y ESP32-S3 Inalambrico
echo  Modo: Wi-Fi SoftAP (http://192.168.4.1/data)
echo  1. Conecta tu PC a la red Wi-Fi: ESP32-GasSensor
echo  2. Ejecuta este programa
echo  Tesis UTEC 2026
echo ============================================================
cd /d "%~dp0"
python visor_gas_python.py --wifi 192.168.4.1
pause
