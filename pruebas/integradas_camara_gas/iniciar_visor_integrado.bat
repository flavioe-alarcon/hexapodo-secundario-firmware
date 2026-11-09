@echo off
title Visor Integrado ESP32-S3 (Camara UVC + Sensor Gas MiCS-5524)
echo ============================================================
echo  Iniciando Visor Integrado Inalambrico (Wi-Fi)
echo  Tesis UTEC 2026 - Conecta tu laptop a: ESP32S3-CAM
echo  Clave Wi-Fi: camara123
echo  IP ESP32-S3: 192.168.4.1
echo ============================================================
cd /d "%~dp0"
python visor_integrado_python.py http://192.168.4.1
pause
