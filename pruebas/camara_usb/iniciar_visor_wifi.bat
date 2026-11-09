@echo off
title Visor ESP32-S3 Camara UVC - Wi-Fi (OpenCV)
echo ============================================================
echo  Iniciando Visor de Camara UVC Inalambrico (Wi-Fi)
echo  Tesis UTEC 2026 - Conecta tu laptop a: ESP32S3-CAM
echo  Clave Wi-Fi: camara123
echo  URL: http://192.168.4.1/stream
echo ============================================================
cd /d "%~dp0"
python visor_camara_wifi.py http://192.168.4.1/stream
pause
